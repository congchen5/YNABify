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

# Configuration
DEBUG_TRANSACTION_LIMIT = 1  # Limit number of transactions to process for debugging
DATE_BUFFER_DAYS = 5  # Number of days +/- to search for matching transactions
DRY_RUN = False  # When True, run without making any modifications (no email labels, no YNAB updates)
REPROCESS = False  # When True, reprocess emails labeled 'processed' (but still skip 'matched')


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

    if REPROCESS:
        print("⚠️  REPROCESS MODE - Will reprocess 'processed' emails")
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
    since_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    ynab_transactions = ynab_client.get_transactions(since_date=since_date)
    print(f"Found {len(ynab_transactions)} YNAB transactions in the last 30 days")

    # Get transactions from email if available
    if email_client:
        print("\n=== Processing Email Transactions ===\n")

        # Initialize integrations
        amazon_integration = AmazonIntegration(ynab_client, email_client, date_buffer_days=DATE_BUFFER_DAYS, dry_run=DRY_RUN, reprocess=REPROCESS)
        venmo_integration = VenmoIntegration(ynab_client, email_client, dry_run=DRY_RUN, reprocess=REPROCESS)

        # Initialize email processor with integrations
        email_processor = EmailProcessor(
            email_client=email_client,
            amazon_integration=amazon_integration,
            venmo_integration=venmo_integration,
            limit=DEBUG_TRANSACTION_LIMIT,
            reprocess=REPROCESS
        )

        # Process all emails once (central processing loop)
        results = email_processor.process_emails(ynab_transactions=ynab_transactions)

        # Summary for Amazon
        amazon_matches = results.get('amazon', [])
        if amazon_matches:
            print(f"\n=== Amazon Summary ===")
            print(f"Found {len(amazon_matches)} Amazon matches")
            print(f"\nTo update these transactions, the bot would:")
            print(f"  1. Update the memo with item details + order link")
            print(f"  2. Keep the transaction UNAPPROVED (you review in YNAB)")
            print(f"  3. Mark the email as read")
        elif amazon_matches is not None:
            print("\n✗ No matches found between Amazon emails and YNAB transactions")

        # Summary for Venmo
        venmo_transactions = results.get('venmo', [])
        if venmo_transactions:
            print(f"\n=== Venmo Summary ===")
            print(f"Found {len(venmo_transactions)} Venmo transactions")

        email_client.disconnect()

    print("\n✓ YNABify completed successfully!")


if __name__ == "__main__":
    main()
