#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from email_client import EmailClient
from amazon_integration import AmazonIntegration
from ynab_client import YNABClient

load_dotenv()

# Initialize clients
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
    # Search for ALL emails (including matched ones)
    email_client.connection.select('INBOX')
    _, message_numbers = email_client.connection.search(None, 'ALL')

    emails = []
    for num in message_numbers[0].split():
        _, msg_data = email_client.connection.fetch(num, '(RFC822)')
        import email as email_module
        email_body = msg_data[0][1]
        email_message = email_module.message_from_bytes(email_body)

        subject = email_client._decode_header(email_message['Subject'])

        if 'Sankoly' in subject:
            body = email_client._get_email_body(email_message)
            emails.append({
                'id': num.decode(),
                'from': email_message['From'],
                'subject': subject,
                'date': email_message['Date'],
                'body': body
            })

    sankoly_emails = emails

    print(f"Found {len(sankoly_emails)} Sankoly emails:\n")

    for idx, email_dict in enumerate(sankoly_emails, 1):
        print(f"=== Email #{idx} ===")
        print(f"Subject: {email_dict['subject']}")
        print(f"Date header: {email_dict['date']}")
        print(f"From: {email_dict['from']}")

        # Parse with Amazon integration
        parsed = amazon.parse_email(email_dict)

        if parsed:
            print(f"\nParsed transaction:")
            print(f"  Date: {parsed['date']}")
            print(f"  Amount: ${parsed['amount']}")
            print(f"  Order: {parsed['order_number']}")
            print(f"  Item name from subject: {parsed.get('item_name_from_subject', 'NOT FOUND')}")
            print(f"  Order details URL: {parsed.get('order_details_url', 'NOT FOUND')}")

            # Format memo
            memo = amazon.format_memo(parsed)
            print(f"  Formatted memo: {memo}")
        else:
            print("  Failed to parse")

        print()

    email_client.disconnect()
