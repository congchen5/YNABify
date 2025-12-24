#!/usr/bin/env python3
"""
Detailed Venmo email analysis - examine full email content
"""

import os
import re
from dotenv import load_dotenv
from email_client import EmailClient
import email
from email.header import decode_header
from bs4 import BeautifulSoup

load_dotenv()

# Initialize Email client
email_address = os.getenv('EMAIL_ADDRESS')
email_password = os.getenv('EMAIL_APP_PASSWORD')
imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))

email_client = EmailClient(email_address, email_password, imap_server, imap_port)

if email_client.connect():
    print("=== Detailed Venmo Email Analysis ===\n")

    email_client.connection.select('INBOX')
    _, message_numbers = email_client.connection.search(None, 'ALL')

    venmo_transaction_emails = []

    for num in message_numbers[0].split():
        _, msg_data = email_client.connection.fetch(num, '(RFC822)')
        email_body = msg_data[0][1]
        email_message = email.message_from_bytes(email_body)

        sender = email_message['From']
        if sender and '@venmo.com' in sender.lower():
            subject = email_message['Subject']
            if subject:
                decoded_parts = decode_header(subject)
                decoded_subject = ""
                for part, encoding in decoded_parts:
                    if isinstance(part, bytes):
                        decoded_subject += part.decode(encoding or 'utf-8', errors='ignore')
                    else:
                        decoded_subject += part
            else:
                decoded_subject = "(No subject)"

            # Only transaction emails (paid/received)
            if 'paid' in decoded_subject.lower():
                # Get full email body
                body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        if part.get_content_type() == "text/html":
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            break
                        elif part.get_content_type() == "text/plain" and not body:
                            body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                else:
                    body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')

                venmo_transaction_emails.append({
                    'subject': decoded_subject,
                    'date': email_message['Date'],
                    'body_html': body
                })

    email_client.disconnect()

    print(f"Found {len(venmo_transaction_emails)} Venmo transaction emails\n")
    print("=" * 100)

    for idx, email_info in enumerate(venmo_transaction_emails, 1):
        print(f"\n{'=' * 100}")
        print(f"EMAIL #{idx}")
        print(f"{'=' * 100}")
        print(f"Subject: {email_info['subject']}")
        print(f"Date: {email_info['date']}")
        print(f"\nHTML Body Structure:")
        print("-" * 100)

        # Parse HTML
        soup = BeautifulSoup(email_info['body_html'], 'html.parser')

        # Show all text content
        print("\nAll Text Content:")
        text = soup.get_text(separator=' | ')
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        print(text[:1500])  # First 1500 chars

        print("\n" + "-" * 100)
        print("\nAll Links:")
        for link in soup.find_all('a', href=True):
            print(f"  Text: {link.get_text().strip()}")
            print(f"  Href: {link['href']}")
            print()

        print("\n" + "-" * 100)
        print("\nSearching for potential description/note:")

        # Look for common patterns
        # Try to find divs, spans, or other elements that might contain the note
        for tag in soup.find_all(['div', 'span', 'p', 'td']):
            text = tag.get_text().strip()
            if text and len(text) > 3 and len(text) < 200:
                # Skip common UI elements
                if text not in ['You paid', 'paid you', 'View Transaction', 'Download the app']:
                    print(f"  - {text}")

else:
    print("Failed to connect to email")
