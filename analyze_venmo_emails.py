#!/usr/bin/env python3
"""
Analyze Venmo email structure to understand patterns for transaction creation
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
    print("=== Fetching ALL Venmo Emails ===\n")

    email_client.connection.select('INBOX')

    # Search for all emails
    _, message_numbers = email_client.connection.search(None, 'ALL')

    venmo_emails = []

    print(f"Checking emails for Venmo patterns...\n")

    for num in message_numbers[0].split():
        _, msg_data = email_client.connection.fetch(num, '(RFC822)')

        email_body = msg_data[0][1]
        email_message = email.message_from_bytes(email_body)

        # Get sender and subject
        sender = email_message['From']
        subject = email_message['Subject']
        date = email_message['Date']

        # Decode subject
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

        # Check if it's a Venmo email
        is_venmo = False
        if sender and '@venmo.com' in sender.lower():
            is_venmo = True
        elif decoded_subject and 'venmo' in decoded_subject.lower():
            is_venmo = True

        if is_venmo:
            # Get email body
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/html":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    elif part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
            else:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')

            venmo_emails.append({
                'subject': decoded_subject,
                'from': sender,
                'date': date,
                'body': body[:1000]  # First 1000 chars
            })

    email_client.disconnect()

    print(f"Found {len(venmo_emails)} Venmo emails\n")
    print("=" * 100)
    print("\nVENMO EMAIL ANALYSIS:\n")
    print("=" * 100)

    for idx, email_info in enumerate(venmo_emails[:10], 1):  # Show first 10
        print(f"\n[{idx}] Subject: {email_info['subject']}")
        print(f"    From: {email_info['from']}")
        print(f"    Date: {email_info['date']}")
        print(f"    Body Preview (first 1000 chars):")
        print("    " + "-" * 80)

        # Parse body with BeautifulSoup to get clean text
        soup = BeautifulSoup(email_info['body'], 'html.parser')
        text = soup.get_text()
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        print(f"    {text[:500]}")
        print("    " + "-" * 80)

    if len(venmo_emails) > 10:
        print(f"\n... and {len(venmo_emails) - 10} more emails")

    print("\n" + "=" * 100)
    print("\nSUBJECT PATTERN ANALYSIS:")
    print("=" * 100)

    # Analyze subject patterns
    patterns = {}
    for email_info in venmo_emails:
        subject = email_info['subject']

        if 'paid you' in subject.lower():
            patterns.setdefault('received_payment', []).append(subject)
        elif 'you paid' in subject.lower():
            patterns.setdefault('sent_payment', []).append(subject)
        elif 'charged you' in subject.lower():
            patterns.setdefault('charged', []).append(subject)
        else:
            patterns.setdefault('other', []).append(subject)

    for pattern_name, subjects in patterns.items():
        print(f"\n{pattern_name.upper()} ({len(subjects)} emails):")
        for subject in subjects[:5]:  # Show first 5 of each pattern
            print(f"  - {subject}")
        if len(subjects) > 5:
            print(f"  ... and {len(subjects) - 5} more")

else:
    print("Failed to connect to email")
