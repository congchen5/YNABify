#!/usr/bin/env python3
"""
User Detection Module
Detects which user (Cong or Margi) a transaction belongs to based on email headers and content.
"""

from typing import Optional


class UserDetector:
    """Detect which user (Cong or Margi) a transaction belongs to"""

    # Configuration (CONFIRMED with YNAB)
    USER_CONFIG = {
        'cong': {
            'emails': ['congchen5@gmail.com'],
            'names': ['Cong Chen', 'Cong'],
            'venmo_account': 'Cong Venmo',  # ✓ Confirmed in YNAB
            'amazon_account': 'Cong Amazon Card',  # ✓ Confirmed in YNAB
            'validate_amazon_name': False  # Cong doesn't share Amazon account
        },
        'margi': {
            'emails': ['margi.kim@gmail.com'],
            'names': ['Margi Kim', 'Margaret Kim', 'Margi', 'Margaret'],
            'venmo_account': 'Margi Venmo',  # ✓ Confirmed in YNAB
            'amazon_account': 'Margi Amazon Card',  # ✓ Confirmed in YNAB
            'validate_amazon_name': True  # Margi shares Amazon with family
        }
    }

    def detect_user_from_email(self, email_dict: dict) -> Optional[str]:
        """
        Detect user from email headers and content

        Priority:
        1. Check 'To' header against known email addresses
        2. Check 'From' header (for direct emails, not forwarded)
        3. Parse email body/subject for user names

        Args:
            email_dict: Dictionary with keys 'to', 'from', 'subject', 'body'

        Returns:
            'cong', 'margi', or None if cannot determine
        """
        # Priority 1: Check To header
        to_header = email_dict.get('to', '').lower()
        if to_header:
            for user, config in self.USER_CONFIG.items():
                for email in config['emails']:
                    if email.lower() in to_header:
                        return user

        # Priority 2: Check From header (for direct emails)
        from_header = email_dict.get('from', '').lower()
        if from_header:
            for user, config in self.USER_CONFIG.items():
                for email in config['emails']:
                    if email.lower() in from_header:
                        return user

        # Priority 3: Parse email body and subject for user names
        subject = email_dict.get('subject', '').lower()
        body = email_dict.get('body', '').lower()
        combined_text = f"{subject} {body}"

        # Check for each user's names in the text
        for user, config in self.USER_CONFIG.items():
            for name in config['names']:
                if name.lower() in combined_text:
                    return user

        # Could not determine user
        return None

    def get_account_name(self, user: str, account_type: str) -> Optional[str]:
        """
        Get YNAB account name for user

        Args:
            user: 'cong' or 'margi'
            account_type: 'venmo' or 'amazon'

        Returns:
            Account name string (e.g., "Cong Venmo"), or None if invalid
        """
        if user not in self.USER_CONFIG:
            return None

        account_key = f"{account_type}_account"
        return self.USER_CONFIG[user].get(account_key)

    def should_validate_amazon_name(self, user: str) -> bool:
        """
        Check if Amazon order recipient name should be validated for this user

        Args:
            user: 'cong' or 'margi'

        Returns:
            True if validation required (Margi shares account), False otherwise
        """
        if user not in self.USER_CONFIG:
            return False

        return self.USER_CONFIG[user].get('validate_amazon_name', False)

    def validate_amazon_recipient(self, user: str, email_body: str) -> bool:
        """
        Validate that an Amazon order is actually for the specified user

        This is specifically for Margi who shares her Amazon account with family.
        We check that the recipient name in the email matches the user's names.

        Args:
            user: 'cong' or 'margi'
            email_body: Full email body text

        Returns:
            True if recipient matches user (or validation not required), False otherwise
        """
        # If validation not required for this user, always return True
        if not self.should_validate_amazon_name(user):
            return True

        # Check if any of the user's names appear in the email body
        # (Amazon emails typically include recipient name in shipping section)
        email_body_lower = email_body.lower()
        user_config = self.USER_CONFIG.get(user, {})
        user_names = user_config.get('names', [])

        for name in user_names:
            if name.lower() in email_body_lower:
                return True

        # Recipient name not found - likely a family member's order
        return False
