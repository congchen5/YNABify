"""
Venmo Integration - Parse Venmo emails and create YNAB transactions
"""

import re
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup


class VenmoIntegration:
    def __init__(self, ynab_client, email_client, user_detector=None, dry_run=False, category_classifier=None):
        """
        Initialize Venmo integration

        Args:
            ynab_client: YNABClient instance
            email_client: EmailClient instance
            user_detector: UserDetector instance for multi-user support (optional)
            dry_run: If True, don't make any modifications (default: False)
            category_classifier: CategoryClassifier instance for automatic categorization (optional)
        """
        self.ynab_client = ynab_client
        self.email_client = email_client
        self.user_detector = user_detector
        self.category_classifier = category_classifier
        self.dry_run = dry_run
        self.venmo_account_id = None  # Will be set when we fetch accounts
        self._account_cache = {}  # Cache for account ID lookups

        # Track classification statistics
        self.classification_stats = {
            'attempted': 0,
            'classified': 0,
            'no_match': 0
        }

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
                # Remove day name and timezone
                date_part = date_str.split(',')[1].strip()  # " 6 Dec 2025 04:23:26 +0000"
                date_without_tz = date_part.rsplit(' ', 1)[0]  # Remove timezone: "6 Dec 2025 04:23:26"
                transaction_date = datetime.strptime(date_without_tz, '%d %b %Y %H:%M:%S')
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

        # Get all YNAB accounts for dynamic lookup
        accounts = self.ynab_client.get_accounts()

        # Build account cache by name
        account_by_name = {account.name: account for account in accounts}

        transactions = []

        # Parse each email with user detection
        for email_dict in emails:
            # Detect which user this email belongs to
            user = None
            if self.user_detector:
                user = self.user_detector.detect_user_from_email(email_dict)
                if not user:
                    print(f"  ⚠ Could not determine user for email: {email_dict['subject'][:60]}")
                    continue
            else:
                # Fallback: assume Cong if no user detector provided (backwards compatibility)
                user = 'cong'

            # Get the appropriate Venmo account for this user
            account_name = self.user_detector.get_account_name(user, 'venmo') if self.user_detector else "Cong Venmo"
            venmo_account = account_by_name.get(account_name)

            if not venmo_account:
                print(f"  ⚠ Could not find '{account_name}' account in YNAB")
                continue

            # Parse the email
            parsed = self.parse_email(email_dict)
            if parsed:
                # Add user and account info to parsed transaction
                parsed['user'] = user
                parsed['account_name'] = account_name
                parsed['account_id'] = venmo_account.id
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
            user_label = f"[{txn['user'].upper()}]" if txn.get('user') else ""
            account_label = f"({txn['account_name']})" if txn.get('account_name') else ""
            print(f"  {date_str}: {amount_str} ({direction}) - {txn['name']} {user_label} {account_label}")
            if txn['description']:
                print(f"    Description: {txn['description']}")

            # Check for duplicates
            duplicate = self._check_duplicate(txn, ynab_transactions)
            if duplicate:
                print(f"    ⚠ Duplicate found in YNAB (skipping)")
                # Mark as created if duplicate (prevents retry)
                if self.dry_run:
                    print(f"    [DRY RUN] Would mark email as created")
                else:
                    self.email_client.label_as_created(txn['email_id'])
                    print(f"    ✓ Marked email as created")
                continue

            # Classify transaction if classifier is available
            if self.category_classifier:
                self.classification_stats['attempted'] += 1

                # Extract text for classification
                text = f"{txn['name']} {txn.get('description', '')}".strip()
                print(f"    🤖 Attempting to classify: '{text}'...")

                category_id = self.category_classifier.classify_venmo_transaction(txn)
                if category_id:
                    self.classification_stats['classified'] += 1
                    category_name = self.category_classifier.get_category_name(category_id)
                    txn['category_id'] = category_id
                    print(f"    ✓ Suggested category: {category_name}")
                else:
                    self.classification_stats['no_match'] += 1
                    txn['category_id'] = None
                    print(f"    ⚠ No confident category classification found")
            else:
                txn['category_id'] = None

            # Create YNAB transaction
            if self.dry_run:
                print(f"    [DRY RUN] Would create YNAB transaction")
                print(f"    [DRY RUN] Would mark email as created")
            else:
                success = self._create_ynab_transaction(txn)
                if success:
                    created_transactions.append(txn)
                    self.email_client.label_as_created(txn['email_id'])
                    print(f"    ✓ Created YNAB transaction")
                    print(f"    ✓ Marked email as created (will retry until created)")
                else:
                    print(f"    ✗ Failed to create YNAB transaction (will retry next run)")

        return created_transactions

    def _check_duplicate(self, venmo_txn: Dict, ynab_transactions: List) -> bool:
        """
        Check if a Venmo transaction already exists in YNAB
        Checks within ±1 day of the transaction date

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

        # Define date range (±1 day)
        date_min = venmo_date - timedelta(days=1)
        date_max = venmo_date + timedelta(days=1)

        # Check for duplicates in YNAB
        for ynab_txn in ynab_transactions:
            # Only check transactions in the specific Venmo account
            if ynab_txn.account_id != venmo_txn.get('account_id'):
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
                account_id=venmo_txn['account_id'],
                date=date_str,
                amount=amount_milliunits,
                payee_name=venmo_txn['name'],
                memo=venmo_txn['memo'],
                category_id=venmo_txn.get('category_id'),
                cleared='cleared'
            )
            return result is not None

        except Exception as e:
            print(f"    Error creating YNAB transaction: {e}")
            import traceback
            traceback.print_exc()
            return False
