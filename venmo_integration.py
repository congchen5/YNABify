"""
Venmo Integration - Parse Venmo emails and create YNAB transactions
"""

import re
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup


class VenmoIntegration:
    def __init__(self, ynab_client, email_client, date_buffer_days=5, dry_run=False, reprocess=False):
        """
        Initialize Venmo integration

        Args:
            ynab_client: YNABClient instance
            email_client: EmailClient instance
            date_buffer_days: Number of days +/- to check for duplicates (default: 5)
            dry_run: If True, don't make any modifications (default: False)
            reprocess: If True, reprocess emails with 'processed' label (default: False)
        """
        self.ynab_client = ynab_client
        self.email_client = email_client
        self.date_buffer_days = date_buffer_days
        self.dry_run = dry_run
        self.reprocess = reprocess
        self.venmo_account_id = None  # Will be set when we fetch accounts

    def parse_email(self, email_dict: Dict) -> Optional[Dict]:
        """
        Parse Venmo transaction notification email
        Handles both sent and received payments.

        Args:
            email_dict: Email dictionary from EmailClient.get_unprocessed_emails

        Returns:
            Dictionary with Venmo transaction details or None
        """
        try:
            body = email_dict['body']
            subject = email_dict['subject']

            # Skip non-transaction emails (like monthly summaries)
            if 'transaction history' in subject.lower():
                return None

            # Parse subject line: "You paid NAME $AMOUNT" or "NAME paid you $AMOUNT"
            sent_match = re.search(r'You paid\s+(.+?)\s+\$?([\d,]+\.\d{2})', subject, re.IGNORECASE)
            received_match = re.search(r'(.+?)\s+paid you\s+\$?([\d,]+\.\d{2})', subject, re.IGNORECASE)

            if sent_match:
                name = sent_match.group(1).strip()
                amount = float(sent_match.group(2).replace(',', ''))
                is_received = False
            elif received_match:
                name = received_match.group(1).strip()
                amount = float(received_match.group(2).replace(',', ''))
                is_received = True
            else:
                print(f"  Could not parse Venmo subject: {subject}")
                return None

            # Extract description/note from body
            # Pattern: amount followed by description, then "See transaction"
            soup = BeautifulSoup(body, 'html.parser')
            text = soup.get_text()

            # Look for text between amount and "See transaction"
            description_pattern = rf'\$\s*{amount:.2f}.*?([A-Za-z0-9\s,\.\-\'"]+?)\s*See transaction'
            desc_match = re.search(description_pattern, text, re.IGNORECASE | re.DOTALL)

            description = None
            if desc_match:
                desc_text = desc_match.group(1).strip()
                # Clean up: remove extra whitespace and common UI text
                desc_text = re.sub(r'\s+', ' ', desc_text)
                # Filter out UI elements
                if desc_text and desc_text.lower() not in ['you paid', 'paid you'] and len(desc_text) > 2:
                    description = desc_text

            # Extract date from email date header
            try:
                date_str = email_dict['date']
                # Parse format: "Sat, 6 Dec 2025 04:23:26 +0000"
                transaction_date = datetime.strptime(date_str.split(',')[1].strip()[:20], '%d %b %Y %H:%M:%S')
            except Exception as e:
                print(f"  Warning: Could not parse date '{email_dict.get('date')}', using today: {e}")
                transaction_date = datetime.now()

            # Build memo
            if is_received:
                memo = f"{name} paid you"
            else:
                memo = f"You paid {name}"

            if description:
                memo += f" - {description}"

            return {
                'source': 'venmo',
                'date': transaction_date,
                'amount': amount,
                'is_received': is_received,
                'name': name,
                'description': description,
                'memo': memo,
                'email_subject': subject,
                'email_id': email_dict['id']
            }

        except Exception as e:
            print(f"  Error parsing Venmo email: {e}")
            import traceback
            traceback.print_exc()
            return None

    def process_email_batch(self, emails: List[Dict], ynab_transactions: List = None) -> List[Dict]:
        """
        Process a batch of pre-fetched Venmo emails: parse and create YNAB transactions
        This is the NEW method used by EmailProcessor.

        Args:
            emails: List of email dictionaries (pre-fetched and classified as Venmo)
            ynab_transactions: List of recent YNAB transactions for duplicate detection

        Returns:
            List of created Venmo transactions
        """
        if ynab_transactions is None:
            ynab_transactions = []

        # Find Cong Venmo account
        accounts = self.ynab_client.get_accounts()
        venmo_account = None
        for account in accounts:
            if account.name == "Cong Venmo":
                venmo_account = account
                self.venmo_account_id = account.id
                break

        if not venmo_account:
            print("  ⚠ Could not find 'Cong Venmo' account in YNAB")
            return []

        print(f"  ✓ Found Venmo account: {venmo_account.name} (ID: {venmo_account.id})")

        transactions = []

        # Parse each email
        for email_dict in emails:
            parsed = self.parse_email(email_dict)
            if parsed:
                transactions.append(parsed)

        if not transactions:
            print("  No Venmo transaction emails found")
            return []

        print(f"\nVenmo Transactions ({len(transactions)}):")
        created_transactions = []

        for txn in transactions:
            date_str = txn['date'].strftime('%Y-%m-%d')
            amount_str = f"${txn['amount']:.2f}" if txn['amount'] else "N/A"
            direction = "RECEIVED" if txn['is_received'] else "SENT"
            print(f"  {date_str}: {amount_str} ({direction}) - {txn['name']}")
            if txn['description']:
                print(f"    Description: {txn['description']}")

            # Check for duplicates
            duplicate = self._check_duplicate(txn, ynab_transactions)
            if duplicate:
                print(f"    ⚠ Duplicate found in YNAB (skipping)")
                # Still mark as processed
                if self.dry_run:
                    print(f"    [DRY RUN] Would mark email as processed")
                else:
                    self.email_client.label_as_processed(txn['email_id'])
                    print(f"    ✓ Marked email as processed")
                continue

            # Create YNAB transaction
            if self.dry_run:
                print(f"    [DRY RUN] Would create YNAB transaction")
                print(f"    [DRY RUN] Would mark email as processed + created")
            else:
                success = self._create_ynab_transaction(txn)
                if success:
                    created_transactions.append(txn)
                    self.email_client.label_as_processed(txn['email_id'])
                    self.email_client.label_as_created(txn['email_id'])
                    print(f"    ✓ Created YNAB transaction")
                    print(f"    ✓ Marked email as processed + created")
                else:
                    print(f"    ✗ Failed to create YNAB transaction")

        return created_transactions

    def _check_duplicate(self, venmo_txn: Dict, ynab_transactions: List) -> bool:
        """
        Check if a Venmo transaction already exists in YNAB
        Uses DATE_BUFFER_DAYS to check within ±N days of the transaction date

        Args:
            venmo_txn: Parsed Venmo transaction
            ynab_transactions: List of recent YNAB transactions

        Returns:
            True if duplicate found, False otherwise
        """
        from datetime import timedelta

        venmo_date = venmo_txn['date']
        venmo_amount = venmo_txn['amount']

        # Convert to YNAB milliunits
        if venmo_txn['is_received']:
            venmo_amount_milliunits = int(venmo_amount * 1000)  # Positive for inflow
        else:
            venmo_amount_milliunits = int(-venmo_amount * 1000)  # Negative for outflow

        # Define date range
        date_min = venmo_date - timedelta(days=self.date_buffer_days)
        date_max = venmo_date + timedelta(days=self.date_buffer_days)

        # Check for duplicates in YNAB
        for ynab_txn in ynab_transactions:
            # Only check transactions in the Venmo account
            if ynab_txn.account_id != self.venmo_account_id:
                continue

            # Parse YNAB transaction date
            try:
                ynab_date = datetime.strptime(ynab_txn.date, '%Y-%m-%d')
            except:
                continue

            # Check if within date range
            if not (date_min <= ynab_date <= date_max):
                continue

            # Check if amount matches
            if ynab_txn.amount == venmo_amount_milliunits:
                return True

        return False

    def _create_ynab_transaction(self, venmo_txn: Dict) -> bool:
        """
        Create a YNAB transaction from a Venmo transaction

        Args:
            venmo_txn: Parsed Venmo transaction

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert amount to YNAB milliunits
            if venmo_txn['is_received']:
                amount_milliunits = int(venmo_txn['amount'] * 1000)  # Positive for inflow
            else:
                amount_milliunits = int(-venmo_txn['amount'] * 1000)  # Negative for outflow

            # Format date as YYYY-MM-DD
            date_str = venmo_txn['date'].strftime('%Y-%m-%d')

            # Call YNAB API to create transaction
            result = self.ynab_client.create_transaction(
                account_id=self.venmo_account_id,
                date=date_str,
                amount=amount_milliunits,
                payee_name=venmo_txn['name'],
                memo=venmo_txn['memo'],
                category_id=None
            )
            return result is not None

        except Exception as e:
            print(f"    Error creating YNAB transaction: {e}")
            import traceback
            traceback.print_exc()
            return False
