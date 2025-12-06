"""
Email Client for parsing Amazon and Venmo transaction emails
"""

import imaplib
import email
from email.header import decode_header
from typing import List, Dict, Optional
from datetime import datetime
import re
from bs4 import BeautifulSoup


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

    def parse_amazon_email(self, email_dict: Dict) -> Optional[Dict]:
        """
        Parse Amazon order confirmation email (including forwarded emails)

        Args:
            email_dict: Email dictionary from get_unread_emails

        Returns:
            Dictionary with Amazon order details or None
        """
        try:
            body = email_dict['body']
            soup = BeautifulSoup(body, 'html.parser')

            # Debug: Print more of body to see order details
            print(f"\n  DEBUG: Searching for order number and total...")
            # Look for order number
            order_search = re.search(r'(Order.{0,50}\d{3}-\d{7}-\d{7})', body, re.IGNORECASE | re.DOTALL)
            if order_search:
                print(f"  Found order pattern: {order_search.group(1)[:100]}")
            # Look for various total patterns
            total_patterns = [
                r'Order Total[:\s]*\$?([\d,]+\.\d{2})',
                r'Grand Total[:\s]*\$?([\d,]+\.\d{2})',
                r'Total[:\s]*\$?([\d,]+\.\d{2})',
            ]
            found_total = False
            for pattern in total_patterns:
                total_search = re.search(pattern, body, re.IGNORECASE)
                if total_search:
                    print(f"  Found total with pattern '{pattern}': ${total_search.group(1)}")
                    found_total = True
                    break

            if not found_total:
                # Show all dollar amounts found
                dollar_amounts = re.findall(r'\$(\d+\.\d{2})', body)
                print(f"  Total not found. All dollar amounts in email: {dollar_amounts[:10]}")

            # Extract order number (handle HTML entities and special chars)
            order_match = re.search(r'(\d{3}-\d{7}-\d{7})', body)
            order_number = order_match.group(1) if order_match else None
            if order_number:
                print(f"  Extracted order number: {order_number}")

            # Extract order details link
            order_details_url = None
            if order_number:
                # Construct Amazon order details URL
                order_details_url = f"https://www.amazon.com/gp/your-account/order-details?orderID={order_number}"

            # Also try to find the link in the email
            if not order_details_url:
                # Look for "Order details" or "View order" links
                order_link = soup.find('a', href=re.compile(r'order-details|orderID='))
                if order_link and order_link.get('href'):
                    href = order_link.get('href')
                    # Make sure it's a full URL
                    if href.startswith('http'):
                        order_details_url = href
                    elif href.startswith('/'):
                        order_details_url = f"https://www.amazon.com{href}"

            # Extract total amount
            # Try to find "Order Total" first
            total_match = re.search(r'(?:Order\s+Total|Grand\s+Total)[:\s]*\$?([\d,]+\.\d{2})', body, re.IGNORECASE)

            if not total_match:
                # Fallback: Use the first dollar amount found (usually the order total in forwarded emails)
                all_amounts = re.findall(r'\$(\d+\.\d{2})', body)
                if all_amounts:
                    # The first amount is typically the order total
                    total_match_str = all_amounts[0]
                    amount = float(total_match_str.replace(',', ''))
                    print(f"  Using first dollar amount as total: ${amount}")
                else:
                    amount = None
            else:
                amount = float(total_match.group(1).replace(',', ''))

            # Extract order date from email
            # For forwarded emails, try to extract original date from forwarding header
            order_date = None
            fwd_date_match = re.search(r'Date:\s+[A-Za-z]+,\s+([A-Za-z]+\s+\d+,\s+\d{4})', body)
            if fwd_date_match:
                try:
                    # Parse "Nov 28, 2025" format
                    date_str = fwd_date_match.group(1)
                    order_date = datetime.strptime(date_str, '%b %d, %Y')
                    print(f"  Extracted order date from forwarded header: {order_date.strftime('%Y-%m-%d')}")
                except:
                    pass

            # Fallback to email date if we couldn't parse forwarded date
            if not order_date:
                try:
                    date_str = email_dict['date']
                    order_date = datetime.strptime(date_str.split(',')[1].strip()[:20], '%d %b %Y %H:%M:%S')
                except:
                    order_date = datetime.now()

            # Extract items (basic extraction - Amazon emails vary)
            items = []
            # Look for product names in the email
            item_matches = soup.find_all('a', href=re.compile(r'/dp/[A-Z0-9]+'))
            for item in item_matches[:5]:  # Limit to first 5 items
                item_text = item.get_text(strip=True)
                if item_text and len(item_text) > 5:
                    items.append(item_text)

            if not order_number and not amount:
                return None

            return {
                'source': 'amazon',
                'order_number': order_number,
                'order_details_url': order_details_url,
                'date': order_date,
                'amount': amount,
                'items': items,
                'description': f"Amazon Order {order_number}" if order_number else "Amazon Purchase",
                'email_subject': email_dict['subject']
            }

        except Exception as e:
            print(f"Error parsing Amazon email: {e}")
            return None

    def parse_venmo_email(self, email_dict: Dict) -> Optional[Dict]:
        """
        Parse Venmo transaction notification email

        Args:
            email_dict: Email dictionary from get_unread_emails

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
                'email_subject': subject
            }

        except Exception as e:
            print(f"Error parsing Venmo email: {e}")
            return None

    def get_amazon_transactions(self, limit: int = 50) -> List[Dict]:
        """Get Amazon transactions from unprocessed emails (works with forwarded emails)"""
        emails = self.get_unprocessed_emails(
            subject_contains='Ordered:',  # Match forwarded Amazon order emails
            limit=limit
        )

        transactions = []
        for email_dict in emails:
            parsed = self.parse_amazon_email(email_dict)
            if parsed:
                parsed['email_id'] = email_dict['id']
                transactions.append(parsed)

        return transactions

    def get_venmo_transactions(self, limit: int = 50) -> List[Dict]:
        """Get Venmo transactions from unprocessed emails (works with forwarded emails)"""
        emails = self.get_unprocessed_emails(
            body_contains='venmo@venmo.com',
            limit=limit
        )

        transactions = []
        for email_dict in emails:
            parsed = self.parse_venmo_email(email_dict)
            if parsed:
                parsed['email_id'] = email_dict['id']
                transactions.append(parsed)

        return transactions
