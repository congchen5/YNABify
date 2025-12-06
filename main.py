#!/usr/bin/env python3
"""
YNABify - YNAB Budget Bot
Helps categorize Amazon and Venmo transactions
"""

import os
from dotenv import load_dotenv
from ynab_client import YNABClient
from email_client import EmailClient


def match_amazon_to_ynab(amazon_txn: dict, ynab_transactions: list) -> dict:
    """
    Find matching YNAB transaction for an Amazon email transaction

    Args:
        amazon_txn: Amazon transaction from email
        ynab_transactions: List of YNAB transactions

    Returns:
        Matching YNAB transaction or None
    """
    amazon_date = amazon_txn['date'].date()
    amazon_amount = amazon_txn['amount']

    # Convert to YNAB milliunits (negative for outflow)
    amazon_amount_milliunits = int(-amazon_amount * 1000)

    for ynab_txn in ynab_transactions:
        # Parse YNAB transaction date
        ynab_date = ynab_txn.date

        # Check if dates match (within 1 day tolerance)
        date_diff = abs((amazon_date - ynab_date).days)
        if date_diff > 1:
            continue

        # Check if amount matches (YNAB stores in milliunits)
        if ynab_txn.amount != amazon_amount_milliunits:
            continue

        # Check if payee contains "Amazon"
        payee_name = ynab_txn.payee_name or ""
        if "amazon" in payee_name.lower():
            return ynab_txn

    return None


def format_amazon_memo(transaction: dict) -> str:
    """
    Format memo for Amazon transaction in YNAB

    Args:
        transaction: Amazon transaction dictionary

    Returns:
        Formatted memo string
    """
    memo_parts = []

    # Add items (first 3)
    if transaction.get('items'):
        items = transaction['items'][:3]
        memo_parts.append(', '.join(items))
        if len(transaction['items']) > 3:
            memo_parts.append(f'+{len(transaction["items"]) - 3} more')

    # Add order details link
    if transaction.get('order_details_url'):
        memo_parts.append(transaction['order_details_url'])

    return ' | '.join(memo_parts) if memo_parts else f"Order {transaction.get('order_number', '')}"


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
        print("\n=== Fetching Transactions from Email ===\n")

        # Get Amazon transactions
        print("Fetching Amazon transactions...")
        amazon_transactions = email_client.get_amazon_transactions(limit=10)

        if amazon_transactions:
            print(f"\n=== Amazon Email Transactions ({len(amazon_transactions)}) ===\n")

            matches = []
            for idx, txn in enumerate(amazon_transactions, 1):
                date_str = txn['date'].strftime('%Y-%m-%d')
                amount_str = f"${txn['amount']:.2f}" if txn['amount'] else "N/A"

                print(f"[{idx}] Amazon Email Transaction:")
                print(f"    Date: {date_str}")
                print(f"    Amount: {amount_str}")
                print(f"    Order: {txn['order_number']}")

                # Show items if available
                if txn.get('items'):
                    items_preview = ', '.join(txn['items'][:3])  # Show first 3 items
                    if len(txn['items']) > 3:
                        items_preview += f" +{len(txn['items']) - 3} more"
                    print(f"    Items: {items_preview}")

                # Try to match with YNAB transaction
                ynab_match = match_amazon_to_ynab(txn, ynab_transactions)

                if ynab_match:
                    print(f"    ✓ MATCHED YNAB Transaction:")
                    print(f"      ID: {ynab_match.id}")
                    print(f"      Payee: {ynab_match.payee_name}")
                    print(f"      Amount: ${ynab_match.amount / 1000:.2f}")
                    print(f"      Current Memo: {ynab_match.memo or '(empty)'}")
                    print(f"      Approved: {'Yes' if ynab_match.approved else 'No'}")

                    # Show what the new memo would be
                    new_memo = format_amazon_memo(txn)
                    print(f"      Proposed Memo: {new_memo}")

                    matches.append({
                        'amazon': txn,
                        'ynab': ynab_match,
                        'new_memo': new_memo
                    })
                else:
                    print(f"    ✗ No matching YNAB transaction found")

                print()  # Empty line between transactions

            # Summary
            if matches:
                print(f"\n=== Summary ===")
                print(f"Found {len(matches)} matches out of {len(amazon_transactions)} Amazon emails")
                print(f"\nTo update these transactions, the bot would:")
                print(f"  1. Update the memo with item details + order link")
                print(f"  2. Keep the transaction UNAPPROVED (you review in YNAB)")
                print(f"  3. Mark the email as read")
            else:
                print("\n✗ No matches found between Amazon emails and YNAB transactions")
        else:
            print("  No unread Amazon transaction emails found")

        # Get Venmo transactions
        print("\nFetching Venmo transactions...")
        venmo_transactions = email_client.get_venmo_transactions(limit=10)
        if venmo_transactions:
            print(f"\nVenmo Transactions ({len(venmo_transactions)}):")
            for txn in venmo_transactions:
                date_str = txn['date'].strftime('%Y-%m-%d')
                amount_str = f"${txn['amount']:.2f}" if txn['amount'] else "N/A"
                print(f"  {date_str}: {amount_str} - {txn['description']}")
        else:
            print("  No unread Venmo transaction emails found")

        email_client.disconnect()

    print("\n✓ YNABify completed successfully!")


if __name__ == "__main__":
    main()
