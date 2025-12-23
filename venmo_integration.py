"""
Venmo Integration - Parse Venmo emails and create YNAB transactions
"""

import re
from typing import Dict, List, Optional
from datetime import datetime


class VenmoIntegration:
    def __init__(self, ynab_client, email_client, dry_run=False, reprocess=False):
        """
        Initialize Venmo integration

        Args:
            ynab_client: YNABClient instance
            email_client: EmailClient instance
            dry_run: If True, don't make any modifications (default: False)
            reprocess: If True, reprocess emails with 'processed' label (default: False)
        """
        self.ynab_client = ynab_client
        self.email_client = email_client
        self.dry_run = dry_run
        self.reprocess = reprocess

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

            # Determine if it's a payment or charge
            is_payment = 'paid you' in subject.lower() or 'sent you' in subject.lower()
            is_charge = 'charged you' in subject.lower() or 'you paid' in subject.lower()

            # Extract amount
            amount_match = re.search(r'\$?([\d,]+\.\d{2})', subject)
            if not amount_match:
                amount_match = re.search(r'\$?([\d,]+\.\d{2})', body)

            amount = float(amount_match.group(1).replace(',', '')) if amount_match else None

            # For payments received, amount should be positive
            # For charges/payments sent, amount should be negative
            if amount and is_charge:
                amount = -amount

            # Extract person/description from subject
            # Venmo subject format: "PersonName paid you $X.XX"
            person_match = re.search(r'^([^$]+?)(?:paid you|charged you|you paid)', subject, re.IGNORECASE)
            person = person_match.group(1).strip() if person_match else "Unknown"

            # Extract note/description from email body
            note_match = re.search(r'(?:Note|For|Description)[:\s]+["\']?([^"\'<\n]+)', body, re.IGNORECASE)
            note = note_match.group(1).strip() if note_match else ""

            # Extract date from email date
            try:
                date_str = email_dict['date']
                transaction_date = datetime.strptime(date_str.split(',')[1].strip()[:20], '%d %b %Y %H:%M:%S')
            except:
                transaction_date = datetime.now()

            if not amount:
                return None

            description = f"Venmo: {person}"
            if note:
                description += f" - {note}"

            return {
                'source': 'venmo',
                'date': transaction_date,
                'amount': amount,
                'person': person,
                'note': note,
                'description': description,
                'email_subject': subject,
                'email_id': email_dict['id']
            }

        except Exception as e:
            print(f"Error parsing Venmo email: {e}")
            return None

    def process_email_batch(self, emails: List[Dict]) -> List[Dict]:
        """
        Process a batch of pre-fetched Venmo emails: parse and prepare for YNAB creation
        This is the NEW method used by EmailProcessor.

        Args:
            emails: List of email dictionaries (pre-fetched and classified as Venmo)

        Returns:
            List of parsed Venmo transactions
        """
        transactions = []

        # Parse each email
        for email_dict in emails:
            parsed = self.parse_email(email_dict)
            if parsed:
                transactions.append(parsed)

        if not transactions:
            print("  No unread Venmo transaction emails found")
            return transactions

        print(f"\nVenmo Transactions ({len(transactions)}):")
        for txn in transactions:
            date_str = txn['date'].strftime('%Y-%m-%d')
            amount_str = f"${txn['amount']:.2f}" if txn['amount'] else "N/A"
            print(f"  {date_str}: {amount_str} - {txn['description']}")

            # Mark email as processed
            if self.dry_run:
                print(f"  [DRY RUN] Would mark email as processed")
            else:
                self.email_client.label_as_processed(txn['email_id'])
                print(f"  ✓ Marked email as processed")

        return transactions
