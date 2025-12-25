#!/usr/bin/env python3
import os
import re
from dotenv import load_dotenv
from email_client import EmailClient
from bs4 import BeautifulSoup

load_dotenv()

email_address = os.getenv('EMAIL_ADDRESS')
email_password = os.getenv('EMAIL_APP_PASSWORD')
imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))

email_client = EmailClient(email_address, email_password, imap_server, imap_port)

if email_client.connect():
    email_client.connection.select('INBOX')
    _, message_numbers = email_client.connection.search(None, 'ALL')

    import email as email_module
    for num in message_numbers[0].split():
        _, msg_data = email_client.connection.fetch(num, '(RFC822)')
        email_body = msg_data[0][1]
        email_message = email_module.message_from_bytes(email_body)

        subject = email_client._decode_header(email_message['Subject'])

        if 'RØDE PSA1+' in subject or 'RODE PSA1+' in subject:
            print(f"Found email: {subject}\n")

            body = email_client._get_email_body(email_message)

            # Extract text
            soup = BeautifulSoup(body, 'html.parser')
            text = soup.get_text()

            # Find all "Grand Total:" occurrences
            grand_totals = re.findall(r'Grand Total:\s*\$?([0-9,]+\.\d{2})', text)
            print(f"Found {len(grand_totals)} Grand Total amounts: {grand_totals}\n")

            # Find all order numbers
            order_numbers = re.findall(r'Order #[^\d]*(\d{3}-\d{7}-\d{7})', text)
            print(f"Found {len(order_numbers)} Order numbers: {order_numbers}\n")

            # Show text around each Grand Total
            for idx, total in enumerate(grand_totals, 1):
                print(f"=== Grand Total #{idx}: ${total} ===")
                # Find context around this total
                pattern = rf'(.{{0,500}})Grand Total:\s*\$?{re.escape(total)}(.{{0,200}})'
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    before = match.group(1)[-500:].strip()
                    after = match.group(2)[:200].strip()
                    print(f"Context before:\n{before}\n")
                    print(f"Context after:\n{after}\n")
                print()

            break

    email_client.disconnect()
