#!/usr/bin/env python3
"""
Bulk Category Classification Script

Applies CategoryClassifier to ALL existing YNAB transactions across all accounts.
By default, processes ALL transactions (even those with existing categories) because
YNAB's auto-categorization is often incorrect.

Usage:
    python scripts/bulk_categorize.py [--days DAYS] [--skip-categorized] [--dry-run]

Options:
    --days DAYS             Process transactions from last N days (default: 90)
    --skip-categorized      Skip transactions that already have a category (opt-in)
    --dry-run              Run without making modifications
"""

import os
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ynab_client import YNABClient
from category_classifier import CategoryClassifier


def bulk_categorize_transactions(
    ynab_client: YNABClient,
    category_classifier: CategoryClassifier,
    days_back: int = 90,
    skip_categorized: bool = False,
    dry_run: bool = False,
    account_filter: str = None
):
    """
    Bulk categorize YNAB transactions using CategoryClassifier

    Args:
        ynab_client: YNABClient instance
        category_classifier: CategoryClassifier instance
        days_back: Number of days to look back (default: 90)
        skip_categorized: Skip transactions with existing categories (default: False)
        dry_run: Run without making modifications (default: False)
        account_filter: Filter to specific account name (default: None = all accounts)

    Returns:
        Dictionary with statistics
    """
    print(f"\n=== Bulk Category Classification ===")
    print(f"Date range: Last {days_back} days")
    print(f"Skip categorized: {skip_categorized}")
    print(f"Account filter: {account_filter or 'All accounts'}")
    if dry_run:
        print("⚠️  DRY RUN MODE - No modifications will be made")
    print("=" * 80)

    # Fetch transactions
    since_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    print(f"\n📥 Fetching transactions since {since_date}...")
    transactions = ynab_client.get_transactions(since_date=since_date)
    print(f"Found {len(transactions)} total transactions")

    # Filter by account if specified
    if account_filter:
        accounts = ynab_client.get_accounts()
        account_map = {account.id: account.name for account in accounts}
        transactions = [
            txn for txn in transactions
            if account_map.get(txn.account_id, '').lower() == account_filter.lower()
        ]
        print(f"Filtered to {len(transactions)} transactions for account: {account_filter}")

    # Statistics tracking
    stats = {
        'processed': 0,
        'classified': 0,
        'updated': 0,  # Had category, we updated it
        'newly_classified': 0,  # Had no category, we added one
        'skipped': 0,
        'no_match': 0,
        'errors': 0
    }

    # Get category names for display
    def get_category_name(category_id):
        if not category_id:
            return "(None)"
        return category_classifier.get_category_name(category_id) or f"Unknown ({category_id})"

    print(f"\n🔍 Processing transactions...\n")

    for txn in transactions:
        stats['processed'] += 1

        # Optional: Skip if already categorized (opt-in flag)
        if txn.category_id and skip_categorized:
            stats['skipped'] += 1
            continue

        # Extract text from payee + memo for classification
        # For Amazon transactions with item names in memo, prioritize the item name
        text = None
        if txn.payee_name and 'amazon' in txn.payee_name.lower() and txn.memo:
            # Extract item name from memo (text before "Amazon Link:")
            import re
            match = re.match(r'(.+?)(?:\s*Amazon Link:|\s*RETURN:|\.\.\.$)', txn.memo)
            if match:
                item_name = match.group(1).strip()
                if item_name and len(item_name) > 3:
                    text = item_name  # Use just the item name for better classification

        # Fallback to payee + memo
        if not text:
            text = f"{txn.payee_name or ''} {txn.memo or ''}".strip()

        if not text:
            stats['no_match'] += 1
            continue

        # Classify using generic classification
        try:
            category_id = category_classifier.classify_generic_transaction(text)

            if category_id:
                stats['classified'] += 1

                # Determine if update or new classification
                had_category = bool(txn.category_id)
                if had_category:
                    old_cat = get_category_name(txn.category_id)
                    new_cat = get_category_name(category_id)

                    # Skip if category is the same
                    if txn.category_id == category_id:
                        continue

                    print(f"  {txn.date} | {txn.payee_name[:40]:40} | {old_cat:25} → {new_cat}")
                    stats['updated'] += 1
                else:
                    new_cat = get_category_name(category_id)
                    print(f"  {txn.date} | {txn.payee_name[:40]:40} | {'(None)':25} → {new_cat}")
                    stats['newly_classified'] += 1

                # Update transaction category
                if not dry_run:
                    success = ynab_client.update_transaction_category(txn.id, category_id)
                    if not success:
                        print(f"    ✗ Failed to update category")
                        stats['errors'] += 1

            else:
                stats['no_match'] += 1

        except Exception as e:
            print(f"  ✗ Error processing transaction {txn.id}: {e}")
            stats['errors'] += 1

    return stats


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Bulk categorize YNAB transactions')
    parser.add_argument('--days', type=int, default=90, help='Process transactions from last N days (default: 90)')
    parser.add_argument('--skip-categorized', action='store_true', help='Skip transactions that already have a category')
    parser.add_argument('--dry-run', action='store_true', help='Run without making modifications')
    parser.add_argument('--account', type=str, help='Filter to specific account name (e.g., "Cong Amazon Card")')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Check required environment variables
    ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
    budget_id = os.getenv('YNAB_BUDGET_ID')

    if not ynab_token or not budget_id:
        print("Error: Missing YNAB_ACCESS_TOKEN or YNAB_BUDGET_ID in .env file")
        return

    # Initialize clients
    ynab_client = YNABClient(ynab_token, budget_id)
    category_classifier = CategoryClassifier(ynab_client)

    # Test connections
    print("\n=== Testing YNAB Connection ===\n")
    if not ynab_client.test_connection():
        print("✗ Failed to connect to YNAB")
        return
    print("✓ Connected to YNAB")

    # Run bulk categorization
    stats = bulk_categorize_transactions(
        ynab_client=ynab_client,
        category_classifier=category_classifier,
        days_back=args.days,
        skip_categorized=args.skip_categorized,
        dry_run=args.dry_run,
        account_filter=args.account
    )

    # Print summary
    print("\n" + "=" * 80)
    print("=== BULK CATEGORIZATION SUMMARY ===")
    if args.dry_run:
        print("=== ⚠️  DRY RUN MODE - No modifications were made ===")
    print("=" * 80)

    print(f"\n📊 Statistics:")
    print(f"  Total processed: {stats['processed']}")
    print(f"  Classified: {stats['classified']}")
    print(f"    - Updated (had category): {stats['updated']}")
    print(f"    - Newly classified (no category): {stats['newly_classified']}")
    print(f"  No match: {stats['no_match']}")
    print(f"  Skipped (already categorized): {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")

    # Calculate coverage percentage
    if stats['processed'] > 0:
        coverage = (stats['classified'] / stats['processed']) * 100
        print(f"\n📈 Coverage: {coverage:.1f}% of transactions classified")

    print("\n" + "=" * 80)

    if args.dry_run and stats['classified'] > 0:
        print(f"\n⚠️  Dry run complete. Would have updated {stats['classified']} transaction(s).")
        print("Run without --dry-run to apply changes.")
    elif stats['classified'] > 0:
        print(f"\n✓ Successfully updated {stats['classified']} transaction(s)!")


if __name__ == "__main__":
    main()
