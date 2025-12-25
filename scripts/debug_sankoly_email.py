#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from email_client import EmailClient
import email
from email.header import decode_header
import re

load_dotenv()

email_address = os.getenv('EMAIL_ADDRESS')
email_password = os.getenv('EMAIL_APP_PASSWORD')
imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))

email_client = EmailClient(email_address, email_password, imap_server, imap_port)

if email_client.connect():
    email_client.connection.select('INBOX')

    # Search for the specific email
    _, message_numbers = email_client.connection.search(None, 'ALL')

    for num in message_numbers[0].split():
        _, msg_data = email_client.connection.fetch(num, '(RFC822)')
        email_body = msg_data[0][1]
        email_message = email.message_from_bytes(email_body)

        subject = email_client._decode_header(email_message['Subject'])

        if 'Sankoly 4 Pack Downspouts' in subject:
            print(f"Found email: {subject}")
            print(f"Email Date header: {email_message['Date']}")
            print(f"From: {email_message['From']}")

            # Check if forwarded
            if 'Fwd:' in subject or 'Forwarded' in subject:
                print("This is a FORWARDED email")

            # Parse the date like the code does
            from datetime import datetime
            try:
                date_str = email_message['Date']
                parsed = datetime.strptime(date_str.split(',')[1].strip()[:20], '%d %b %Y %H:%M:%S')
                print(f"Parsed date: {parsed.strftime('%Y-%m-%d')}")
            except Exception as e:
                print(f"Date parsing failed: {e}")

            # Get body
            body = email_client._get_email_body(email_message)

            # Look for date patterns
            print("\n=== Looking for dates in body ===")
            date_patterns = [
                r'Date:\s+([A-Za-z]+,\s+[A-Za-z]+\s+\d+,\s+\d{4})',
                r'Ordered on\s+([A-Za-z]+\s+\d+,\s+\d{4})',
                r'Order Date[:\s]+([A-Za-z]+\s+\d+,\s+\d{4})',
                r'(\d{1,2}/\d{1,2}/\d{4})'
            ]

            for pattern in date_patterns:
                matches = re.findall(pattern, body)
                if matches:
                    print(f"Pattern '{pattern}': {matches[:3]}")

            # Show first 2000 chars of body
            print("\n=== First 2000 chars of body ===")
            print(body[:2000])

            # Extract text from HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(body, 'html.parser')
            text = soup.get_text()
            print("\n=== First 2000 chars of text ===")
            print(text[:2000])

            break

    email_client.disconnect()
