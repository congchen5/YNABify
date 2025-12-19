"""
Email Client for generic email handling
"""

import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Optional


class EmailClient:
    def __init__(
        self,
        email_address: str,
        app_password: str,
        imap_server: str = 'imap.gmail.com',
        imap_port: int = 993
    ):
        """
        Initialize email client

        Args:
            email_address: Email address
            app_password: Gmail app password
            imap_server: IMAP server address
            imap_port: IMAP port
        """
        self.email_address = email_address
        self.app_password = app_password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.connection = None

    def connect(self) -> bool:
        """
        Connect to IMAP server

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.email_address, self.app_password)
            print(f"✓ Connected to email successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to email: {e}")
            return False

    def disconnect(self):
        """Disconnect from IMAP server"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass

    def get_unprocessed_emails(
        self,
        sender: Optional[str] = None,
        subject_contains: Optional[str] = None,
        body_contains: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get emails that are NOT labeled as 'processed'

        Args:
            sender: Filter by sender email address
            subject_contains: Filter by subject content
            body_contains: Filter by keyword in body (for forwarded emails)
            limit: Maximum number of emails to fetch

        Returns:
            List of email dictionaries
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            self.connection.select('INBOX')

            # Build search criteria
            search_criteria = []
            if sender:
                search_criteria.append(f'FROM "{sender}"')
            if subject_contains:
                search_criteria.append(f'SUBJECT "{subject_contains}"')
            # Note: IMAP TEXT search is not reliable, so we'll filter body content after fetching

            # Get all matching emails first
            search_string = ' '.join(search_criteria) if search_criteria else 'ALL'
            _, message_numbers = self.connection.search(None, search_string)

            emails = []
            total_checked = 0
            for num in message_numbers[0].split():
                total_checked += 1
                # Check if email has 'processed' label
                _, msg_data = self.connection.fetch(num, '(X-GM-LABELS RFC822)')

                # Parse labels (Gmail-specific) - extract only the X-GM-LABELS part
                labels_str = str(msg_data[0][0])  # Get the first part which contains X-GM-LABELS

                # Debug: print first few to see what we're getting
                if total_checked <= 10:
                    print(f"  Debug: Email {num.decode()}, Labels: {labels_str[:200]}")

                if 'processed' in labels_str.lower():
                    if total_checked <=10:
                        print(f"    Skipped (has 'processed' label)")
                    continue  # Skip emails that are already processed

                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)

                body_text = self._get_email_body(email_message)

                # Filter by body content if specified (for forwarded emails)
                if body_contains:
                    if body_contains.lower() not in body_text.lower():
                        # Debug: show why emails are filtered
                        if total_checked <= 10:
                            subject = self._decode_header(email_message['Subject'])
                            print(f"    Skipped (keyword '{body_contains}' not found): {subject[:80]}")
                        continue  # Skip if keyword not found in body

                subject = self._decode_header(email_message['Subject'])
                emails.append({
                    'id': num.decode(),
                    'from': email_message['From'],
                    'subject': subject,
                    'date': email_message['Date'],
                    'body': body_text
                })

                if total_checked <= 10:
                    print(f"    ✓ MATCHED: {subject[:80]}")

                if len(emails) >= limit:
                    break

            print(f"  Debug: Checked {total_checked} emails, found {len(emails)} unprocessed")
            return emails

        except Exception as e:
            print(f"Error fetching emails: {e}")
            return []

    def mark_as_read(self, email_id: str):
        """Mark an email as read"""
        try:
            self.connection.store(email_id, '+FLAGS', '\\Seen')
        except Exception as e:
            print(f"Error marking email as read: {e}")

    def label_as_processed(self, email_id: str):
        """Label an email as 'processed' (Gmail-specific)"""
        try:
            # Gmail IMAP extension to add label
            self.connection.store(email_id, '+X-GM-LABELS', 'processed')
        except Exception as e:
            print(f"Error labeling email as processed: {e}")

    def _decode_header(self, header: str) -> str:
        """Decode email header"""
        if header is None:
            return ""
        decoded_parts = decode_header(header)
        decoded_header = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_header += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                decoded_header += part
        return decoded_header

    def _get_email_body(self, email_message) -> str:
        """Extract email body (prefer HTML, fallback to plain text)"""
        body = ""
        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                if content_type == "text/html":
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        pass
                elif content_type == "text/plain" and not body:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    except:
                        pass
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(email_message.get_payload())
        return body
