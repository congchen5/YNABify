#!/usr/bin/env python3
"""
YNABify - YNAB Budget Bot
Helps categorize Amazon and Venmo transactions
"""

import os
from dotenv import load_dotenv
from ynab_client import YNABClient
from email_client import EmailClient
from amazon_integration import AmazonIntegration
from venmo_integration import VenmoIntegration
from email_processor import EmailProcessor
from user_detector import UserDetector
from category_classifier import CategoryClassifier

# Configuration
DEBUG_TRANSACTION_LIMIT = 1000  # Limit number of transactions to process for debugging
DATE_BUFFER_DAYS = 5  # Number of days +/- to search for matching transactions
EMAIL_DAYS_BACK = 30  # Only process emails from the last N days (temporarily increased to reprocess older emails)
DRY_RUN = False  # When True, run without making any modifications (no email labels, no YNAB updates)


def check_required_env_vars() -> bool:
    """Check if all required environment variables are set"""
    required_vars = [
        'YNAB_ACCESS_TOKEN',
        'YNAB_BUDGET_ID',
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        print("Error: Missing required environment variables:")
        for var in missing:
            print(f"  - {var}")
        print("\nPlease check SETUP.md for configuration instructions")
        return False

    return True


def test_connections(ynab_client: YNABClient, email_client: EmailClient = None):
    """Test connections to YNAB and Email"""
    print("\n=== Testing Connections ===\n")

    # Test YNAB
    ynab_connected = ynab_client.test_connection()

    # Test Email if credentials provided
    email_connected = False
    if email_client:
        email_connected = email_client.connect()
        if email_connected:
            email_client.disconnect()
    else:
        print("⚠ Email credentials not configured (optional)")

    print("\n=== Connection Summary ===")
    print(f"YNAB:  {'✓ Connected' if ynab_connected else '✗ Failed'}")
    print(f"Email: {'✓ Connected' if email_connected else '✗ Failed or Not Configured'}")

    return ynab_connected and email_connected


def main():
    # Load environment variables
    load_dotenv()

    print("YNABify - YNAB Budget Bot")
    print("=" * 40)

    if DRY_RUN:
        print("⚠️  DRY RUN MODE - No modifications will be made")
        print("=" * 40)

    # Check required environment variables
    if not check_required_env_vars():
        return

    # Initialize YNAB client
    ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
    budget_id = os.getenv('YNAB_BUDGET_ID')
    ynab_client = YNABClient(ynab_token, budget_id)

    # Initialize Email client (optional)
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_APP_PASSWORD')
    imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
    imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))

    email_client = None
    if email_address and email_password:
        email_client = EmailClient(
            email_address,
            email_password,
            imap_server,
            imap_port
        )

    # Test connections
    if not test_connections(ynab_client, email_client):
        print("\n⚠ Some connections failed. Please check your credentials.")
        return

    print("\n=== Fetching Data ===\n")

    # Get YNAB accounts
    accounts = ynab_client.get_accounts()
    if accounts:
        print(f"YNAB Accounts ({len(accounts)}):")
        for account in accounts[:5]:  # Show first 5
            print(f"  - {account.name} (ID: {account.id})")
        if len(accounts) > 5:
            print(f"  ... and {len(accounts) - 5} more")

    # Get recent YNAB transactions for matching
    print("\n=== Fetching Recent YNAB Transactions ===\n")
    from datetime import datetime, timedelta
    # Fetch extra days to account for EMAIL_DAYS_BACK + DATE_BUFFER_DAYS
    since_date = (datetime.now() - timedelta(days=EMAIL_DAYS_BACK + DATE_BUFFER_DAYS + 5)).strftime('%Y-%m-%d')
    ynab_transactions = ynab_client.get_transactions(since_date=since_date)
    print(f"Found {len(ynab_transactions)} YNAB transactions since {since_date}")

    # Initialize category classifier (used for both email processing and bulk categorization)
    print("\n✓ Initializing category classifier")
    category_classifier = CategoryClassifier(ynab_client)

    # Get transactions from email if available
    if email_client:
        print("\n=== Processing Email Transactions ===\n")
        print(f"Processing emails from the last {EMAIL_DAYS_BACK} days")

        # Initialize user detector for multi-user support
        user_detector = UserDetector()
        print("✓ Initialized multi-user support (Cong & Margi)")

        # Initialize integrations
        amazon_integration = AmazonIntegration(ynab_client, email_client, user_detector=user_detector, date_buffer_days=DATE_BUFFER_DAYS, dry_run=DRY_RUN, category_classifier=category_classifier)
        venmo_integration = VenmoIntegration(ynab_client, email_client, user_detector=user_detector, dry_run=DRY_RUN, category_classifier=category_classifier)

        # Initialize email processor with integrations
        email_processor = EmailProcessor(
            email_client=email_client,
            amazon_integration=amazon_integration,
            venmo_integration=venmo_integration,
            limit=DEBUG_TRANSACTION_LIMIT,
            days_back=EMAIL_DAYS_BACK
        )

        # Process all emails once (central processing loop)
        results = email_processor.process_emails(ynab_transactions=ynab_transactions)

        # Get stats
        stats = results.get('stats', {})
        amazon_matches = results.get('amazon', [])
        venmo_transactions = results.get('venmo', [])

        # Count matched vs unmatched for Amazon
        # Note: amazon_matches only contains emails that matched to YNAB
        amazon_matched = len(amazon_matches)
        amazon_total = stats.get('amazon_emails', 0)
        amazon_unmatched = amazon_total - amazon_matched

        email_client.disconnect()

        # Print comprehensive summary
        print("\n" + "=" * 80)
        print("=== RUN SUMMARY ===")
        if DRY_RUN:
            print("=== ⚠️  DRY RUN MODE - No modifications were made ===")
        print("=" * 80)

        print(f"\n📧 Email Processing:")
        print(f"  Total emails processed: {stats.get('total_emails', 0)}")
        print(f"    - Amazon emails: {stats.get('amazon_emails', 0)}")
        print(f"    - Venmo emails: {stats.get('venmo_emails', 0)}")
        print(f"    - Unrecognized: {stats.get('unrecognized_emails', 0)}")

        print(f"\n🔗 YNAB Matching (Amazon):")
        if DRY_RUN:
            print(f"  Would Match & Update: {amazon_matched}")
        else:
            print(f"  Matched & Updated: {amazon_matched}")
        print(f"  Unmatched: {amazon_unmatched}")
        print(f"  Total Amazon: {amazon_total}")

        print(f"\n💸 Venmo Transactions:")
        if DRY_RUN:
            print(f"  Would Create: {len(venmo_transactions)}")
        else:
            print(f"  Created: {len(venmo_transactions)}")

        if amazon_matched > 0:
            if DRY_RUN:
                print(f"\n⚠️  Would update {amazon_matched} YNAB transaction(s) with Amazon details (DRY RUN)")
            else:
                print(f"\n✓ Successfully updated {amazon_matched} YNAB transaction(s) with Amazon details")

        if len(venmo_transactions) > 0:
            if DRY_RUN:
                print(f"⚠️  Would create {len(venmo_transactions)} YNAB transaction(s) from Venmo (DRY RUN)")
            else:
                print(f"✓ Successfully created {len(venmo_transactions)} YNAB transaction(s) from Venmo")

        # Print category classification summary
        amazon_stats = amazon_integration.classification_stats
        venmo_stats = venmo_integration.classification_stats
        total_attempted = amazon_stats['attempted'] + venmo_stats['attempted']
        total_classified = amazon_stats['classified'] + venmo_stats['classified']
        total_no_match = amazon_stats['no_match'] + venmo_stats['no_match']

        if total_attempted > 0:
            print(f"\n🤖 Category Classification:")
            print(f"  Total attempted: {total_attempted}")
            print(f"  Successfully classified: {total_classified}")
            print(f"  No confident match: {total_no_match}")
            if total_attempted > 0:
                coverage = (total_classified / total_attempted) * 100
                print(f"  Coverage: {coverage:.1f}%")

        print("\n" + "=" * 80)

    # Run bulk categorization on all unapproved transactions
    print("\n=== Running Bulk Categorization ===\n")
    print("Categorizing all unapproved transactions across all accounts...")

    if not DRY_RUN:
        try:
            from scripts.bulk_categorize import bulk_categorize_transactions

            # Run bulk categorization (last 90 days)
            bulk_stats = bulk_categorize_transactions(
                ynab_client=ynab_client,
                category_classifier=category_classifier,
                days_back=90,
                skip_categorized=False,
                account_filter=None,
                dry_run=False
            )

            print(f"\n✓ Bulk categorization complete:")
            print(f"  Total processed: {bulk_stats['processed']}")
            print(f"  Classified: {bulk_stats['classified']}")
            print(f"  Updated: {bulk_stats['updated']}")
            print(f"  Newly classified: {bulk_stats['newly_classified']}")
            print(f"  No match: {bulk_stats['no_match']}")

        except Exception as e:
            print(f"⚠ Bulk categorization failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠️  DRY RUN MODE - Skipping bulk categorization")

    print("\n✓ YNABify completed successfully!")


if __name__ == "__main__":
    main()
