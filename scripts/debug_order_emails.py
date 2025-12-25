#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from email_client import EmailClient

load_dotenv()

email_address = os.getenv('EMAIL_ADDRESS')
email_password = os.getenv('EMAIL_APP_PASSWORD')
imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))

email_client = EmailClient(email_address, email_password, imap_server, imap_port)

if email_client.connect():
    email_client.connection.select('INBOX')
    _, message_numbers = email_client.connection.search(None, 'ALL')

    order_number = '111-7143698-7840244'
    emails = []

    import email as email_module
    for num in message_numbers[0].split():
        _, msg_data = email_client.connection.fetch(num, '(RFC822 X-GM-LABELS)')
        email_body = msg_data[0][1]
        email_message = email_module.message_from_bytes(email_body)

        subject = email_client._decode_header(email_message['Subject'])
        body = email_client._get_email_body(email_message)

        if order_number in subject or order_number in body:
            # Get labels
            labels_str = str(msg_data[0][0])

            emails.append({
                'subject': subject,
                'date': email_message['Date'],
                'from': email_message['From'],
                'labels': labels_str
            })

    print(f"Found {len(emails)} email(s) for order {order_number}:\n")

    for idx, e in enumerate(emails, 1):
        print(f"=== Email #{idx} ===")
        print(f"Subject: {e['subject']}")
        print(f"Date: {e['date']}")
        print(f"From: {e['from']}")
        print(f"Labels: {e['labels'][:200]}")
        print()

    email_client.disconnect()
