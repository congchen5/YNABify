"""
Email Processor - Central coordinator for processing emails from all vendors
"""

from typing import List, Dict, Optional
from email_client import EmailClient


class EmailProcessor:
    def __init__(
        self,
        email_client: EmailClient,
        amazon_integration=None,
        venmo_integration=None,
        limit: int = 50,
        reprocess: bool = False
    ):
        """
        Initialize email processor

        Args:
            email_client: EmailClient instance
            amazon_integration: AmazonIntegration instance (optional)
            venmo_integration: VenmoIntegration instance (optional)
            limit: Maximum number of emails to process
            reprocess: If True, reprocess emails with 'processed' label
        """
        self.email_client = email_client
        self.amazon_integration = amazon_integration
        self.venmo_integration = venmo_integration
        self.limit = limit
        self.reprocess = reprocess

    def classify_email(self, email_dict: Dict) -> Optional[str]:
        """
        Classify email by subject line or sender domain

        All emails are forwarded from congchen5@gmail.com, so we primarily
        use subject line patterns to identify the vendor.

        Args:
            email_dict: Email dictionary with 'from' and 'subject' fields

        Returns:
            'amazon', 'venmo', or None if unrecognized
        """
        sender = email_dict.get('from', '').lower()
        subject = email_dict.get('subject', '')

        # Check subject line patterns (for forwarded emails)
        if 'Ordered:' in subject or 'order' in subject.lower():
            return 'amazon'
        elif 'paid you' in subject.lower() or 'you paid' in subject.lower() or 'charged you' in subject.lower():
            return 'venmo'

        # Fallback: domain-based classification (for direct emails)
        if '@amazon.com' in sender:
            return 'amazon'
        elif '@venmo.com' in sender:
            return 'venmo'

        return None

    def process_emails(self, ynab_transactions: List = None) -> Dict[str, List]:
        """
        Fetch and process all unprocessed emails, routing to appropriate integrations

        Args:
            ynab_transactions: List of YNAB transactions (needed for Amazon matching)

        Returns:
            Dictionary with results by vendor: {'amazon': [...], 'venmo': [...]}
        """
        print("\n=== Fetching All Unprocessed Emails ===\n")

        # Fetch ALL unprocessed emails (no vendor-specific filters)
        emails = self.email_client.get_unprocessed_emails(
            limit=self.limit,
            reprocess=self.reprocess
        )

        if not emails:
            print("  No unprocessed emails found")
            return {'amazon': [], 'venmo': []}

        print(f"Found {len(emails)} unprocessed email(s)\n")

        # Classify and route emails
        amazon_emails = []
        venmo_emails = []
        unrecognized_emails = []

        for email_dict in emails:
            vendor = self.classify_email(email_dict)

            if vendor == 'amazon':
                amazon_emails.append(email_dict)
            elif vendor == 'venmo':
                venmo_emails.append(email_dict)
            else:
                unrecognized_emails.append(email_dict)

        print(f"Email Classification:")
        print(f"  Amazon: {len(amazon_emails)}")
        print(f"  Venmo: {len(venmo_emails)}")
        print(f"  Unrecognized: {len(unrecognized_emails)}")

        if unrecognized_emails:
            print(f"\n  Unrecognized emails (will be skipped):")
            for email_dict in unrecognized_emails[:5]:  # Show first 5
                print(f"    - From: {email_dict['from']}, Subject: {email_dict['subject'][:60]}")

        # Process by vendor
        results = {
            'amazon': [],
            'venmo': [],
            'stats': {
                'total_emails': len(emails),
                'amazon_emails': len(amazon_emails),
                'venmo_emails': len(venmo_emails),
                'unrecognized_emails': len(unrecognized_emails)
            }
        }

        # Process Amazon emails
        if amazon_emails and self.amazon_integration:
            print(f"\n=== Processing {len(amazon_emails)} Amazon Email(s) ===\n")
            results['amazon'] = self.amazon_integration.process_email_batch(
                amazon_emails,
                ynab_transactions
            )

        # Process Venmo emails
        if venmo_emails and self.venmo_integration:
            print(f"\n=== Processing {len(venmo_emails)} Venmo Email(s) ===\n")
            results['venmo'] = self.venmo_integration.process_email_batch(venmo_emails)

        return results
