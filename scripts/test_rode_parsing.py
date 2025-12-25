#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from email_client import EmailClient
from amazon_integration import AmazonIntegration
from ynab_client import YNABClient

load_dotenv()

email_address = os.getenv('EMAIL_ADDRESS')
email_password = os.getenv('EMAIL_APP_PASSWORD')
imap_server = os.getenv('EMAIL_IMAP_SERVER', 'imap.gmail.com')
imap_port = int(os.getenv('EMAIL_IMAP_PORT', 993))

email_client = EmailClient(email_address, email_password, imap_server, imap_port)

ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
budget_id = os.getenv('YNAB_BUDGET_ID')
ynab_client = YNABClient(ynab_token, budget_id)

amazon = AmazonIntegration(ynab_client, email_client, date_buffer_days=5, dry_run=True, reprocess=True)

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
            print(f"Found RØDE email: {subject}\n")

            body = email_client._get_email_body(email_message)

            email_dict = {
                'id': num.decode(),
                'from': email_message['From'],
                'subject': subject,
                'date': email_message['Date'],
                'body': body
            }

            print("Parsing with AmazonIntegration...")
            parsed_list = amazon.parse_email(email_dict)

            print(f"\nReturned {len(parsed_list)} transaction(s):\n")

            for idx, txn in enumerate(parsed_list, 1):
                print(f"Transaction #{idx}:")
                print(f"  Order: {txn['order_number']}")
                print(f"  Amount: ${txn['amount']:.2f}")
                print(f"  Item: {txn.get('item_name_from_subject', 'None')}")
                print()

            break

    email_client.disconnect()
