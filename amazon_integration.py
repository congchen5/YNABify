"""
Amazon Integration - Parse Amazon emails and match to YNAB transactions
"""

import re
import html
from typing import Dict, List, Optional
from datetime import datetime
from bs4 import BeautifulSoup


class AmazonIntegration:
    def __init__(self, ynab_client, email_client, date_buffer_days=1, dry_run=False, reprocess=False):
        """
        Initialize Amazon integration

        Args:
            ynab_client: YNABClient instance
            email_client: EmailClient instance
            date_buffer_days: Number of days +/- to search for matching transactions (default: 1)
            dry_run: If True, don't make any modifications (default: False)
            reprocess: If True, reprocess emails with 'processed' label (default: False)
        """
        self.ynab_client = ynab_client
        self.email_client = email_client
        self.date_buffer_days = date_buffer_days
        self.dry_run = dry_run
        self.reprocess = reprocess

    def _extract_return_item_name(self, subject: str) -> Optional[str]:
        """
        Extract item name from return email subject

        Patterns:
        - "Fwd: Return request confirmed for <ITEM_NAME>..."
        - "Fwd: Your return drop off confirmation for <ITEM_NAME>...."

        Args:
            subject: Email subject line

        Returns:
            Extracted item name with HTML entities decoded, or None
        """
        # Strip forwarding prefix
        clean_subject = re.sub(r'^Fwd:\s*', '', subject, flags=re.IGNORECASE)

        # Try pattern 1: "Return request confirmed for ..."
        match = re.search(r'return request confirmed for\s+(.+)', clean_subject, re.IGNORECASE)
        if match:
            item_name = match.group(1).strip()
            # Decode HTML entities (&amp, &quot, etc.)
            item_name = html.unescape(item_name)
            return item_name

        # Try pattern 2: "Your return drop off confirmation for ..."
        match = re.search(r'return drop off confirmation for\s+(.+)', clean_subject, re.IGNORECASE)
        if match:
            item_name = match.group(1).strip()
            # Decode HTML entities (&amp, &quot, etc.)
            item_name = html.unescape(item_name)
            return item_name

        return None

    def parse_email(self, email_dict: Dict) -> Optional[Dict]:
        """
        Parse Amazon order confirmation email (including forwarded emails)
        Handles both purchases and refunds internally.

        Args:
            email_dict: Email dictionary from EmailClient.get_unprocessed_emails

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
                    # Parse format: "Tue, 9 Dec 2025 06:50:15 +0000"
                    # Remove day name and timezone
                    date_part = date_str.split(',')[1].strip()  # "9 Dec 2025 06:50:15 +0000"
                    date_without_tz = date_part.rsplit(' ', 1)[0]  # Remove timezone: "9 Dec 2025 06:50:15"
                    order_date = datetime.strptime(date_without_tz, '%d %b %Y %H:%M:%S')
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

            # Extract item name from subject line
            subject = email_dict['subject']

            # Detect if this is a return transaction
            is_return = 'return' in subject.lower()

            item_name_from_subject = None
            if is_return:
                # For return emails: extract from return-specific patterns
                print(f"  Detected RETURN transaction")
                item_name_from_subject = self._extract_return_item_name(subject)
                if item_name_from_subject:
                    print(f"  Extracted return item: {item_name_from_subject}")
            elif 'Ordered:' in subject:
                # For purchase emails: extract from "Ordered:" pattern
                # Handle formats like: "Ordered: Item..." or "Ordered: 2 'Item...'"
                match = re.search(r'Ordered:.*?["\']([^"\']+)', subject)
                if match:
                    item_name_from_subject = match.group(1).strip()
                    # Keep the "..." to indicate truncation

            return {
                'source': 'amazon',
                'order_number': order_number,
                'order_details_url': order_details_url,
                'date': order_date,
                'amount': amount,
                'items': items,
                'item_name_from_subject': item_name_from_subject,
                'description': f"Amazon Order {order_number}" if order_number else "Amazon Purchase",
                'email_subject': email_dict['subject'],
                'email_id': email_dict['id'],
                'is_return': is_return
            }

        except Exception as e:
            print(f"Error parsing Amazon email: {e}")
            return None

    def match_to_ynab(self, amazon_txn: dict, ynab_transactions: list) -> Optional[dict]:
        """
        Find matching YNAB transaction for an Amazon email transaction
        Handles both purchases (negative/outflow) and returns (positive/inflow)

        Args:
            amazon_txn: Amazon transaction from email
            ynab_transactions: List of YNAB transactions

        Returns:
            Matching YNAB transaction or None
        """
        amazon_date = amazon_txn['date'].date()
        amazon_amount = amazon_txn['amount']
        is_return = amazon_txn.get('is_return', False)

        # Cannot match if amount is None
        if amazon_amount is None:
            return None

        # Convert to YNAB milliunits
        # Returns are positive (inflow), purchases are negative (outflow)
        if is_return:
            amazon_amount_milliunits = int(amazon_amount * 1000)  # Positive for inflow
        else:
            amazon_amount_milliunits = int(-amazon_amount * 1000)  # Negative for outflow

        for ynab_txn in ynab_transactions:
            # Parse YNAB transaction date (convert from string to date object)
            if isinstance(ynab_txn.date, str):
                ynab_date = datetime.strptime(ynab_txn.date, '%Y-%m-%d').date()
            else:
                ynab_date = ynab_txn.date

            # Check if dates match (within configured day tolerance)
            date_diff = abs((amazon_date - ynab_date).days)
            if date_diff > self.date_buffer_days:
                continue

            # Check if amount matches (YNAB stores in milliunits)
            if ynab_txn.amount != amazon_amount_milliunits:
                continue

            # Check if payee contains "Amazon"
            payee_name = ynab_txn.payee_name or ""
            if "amazon" in payee_name.lower():
                return ynab_txn

        return None

    def _build_base_memo(self, transaction: dict) -> str:
        """
        Build the base memo content for Amazon transaction (DRY principle)
        This is reused by both purchases and returns.

        Args:
            transaction: Amazon transaction dictionary

        Returns:
            Base memo string without return prefix
        """
        memo_parts = []

        # Prefer item name from subject line, fall back to parsed items
        if transaction.get('item_name_from_subject'):
            item_name = transaction['item_name_from_subject']
            # If item name already ends with "...", keep it; otherwise add a period
            if not item_name.endswith('...'):
                item_name += '.'
            memo_parts.append(item_name)
        elif transaction.get('items'):
            items = transaction['items'][:3]
            items_text = ', '.join(items)
            if len(transaction['items']) > 3:
                items_text += f' +{len(transaction["items"]) - 3} more'
            memo_parts.append(f"{items_text}.")

        # Add order details link with "Amazon Link: " prefix
        if transaction.get('order_details_url'):
            memo_parts.append(f"Amazon Link: {transaction['order_details_url']}")

        return ' '.join(memo_parts) if memo_parts else f"Order {transaction.get('order_number', '')}"

    def format_memo(self, transaction: dict) -> str:
        """
        Format memo for Amazon transaction in YNAB
        Adds "RETURN: " prefix for return transactions (DRY principle)

        Args:
            transaction: Amazon transaction dictionary

        Returns:
            Formatted memo string: "RETURN: <base_memo>" for returns or "<base_memo>" for purchases
        """
        base_memo = self._build_base_memo(transaction)

        # Add RETURN prefix for return transactions
        if transaction.get('is_return', False):
            return f"RETURN: {base_memo}"

        return base_memo

    def process_email_batch(self, emails: List[Dict], ynab_transactions: List) -> List[Dict]:
        """
        Process a batch of pre-fetched Amazon emails: parse and match to YNAB
        This is the NEW method used by EmailProcessor.

        Args:
            emails: List of email dictionaries (pre-fetched and classified as Amazon)
            ynab_transactions: List of YNAB transactions to match against

        Returns:
            List of matches (dict with 'amazon', 'ynab', 'new_memo' keys)
        """
        matches = []
        amazon_transactions = []

        # Parse each email
        for email_dict in emails:
            parsed = self.parse_email(email_dict)
            if parsed:
                amazon_transactions.append(parsed)

        if not amazon_transactions:
            print("  No unread Amazon transaction emails found")
            return matches

        print(f"\n=== Amazon Email Transactions ({len(amazon_transactions)}) ===\n")

        # Match each Amazon transaction to YNAB
        for idx, txn in enumerate(amazon_transactions, 1):
            date_str = txn['date'].strftime('%Y-%m-%d')
            amount_str = f"${txn['amount']:.2f}" if txn['amount'] else "N/A"
            is_return = txn.get('is_return', False)

            print(f"[{idx}] Amazon Email Transaction {'(RETURN)' if is_return else ''}:")
            print(f"    Date: {date_str}")
            print(f"    Amount: {amount_str}")
            print(f"    Order: {txn['order_number']}")
            if is_return:
                print(f"    Type: RETURN (expecting positive/inflow in YNAB)")

            # Show items if available
            if txn.get('items'):
                items_preview = ', '.join(txn['items'][:3])  # Show first 3 items
                if len(txn['items']) > 3:
                    items_preview += f" +{len(txn['items']) - 3} more"
                print(f"    Items: {items_preview}")

            # Try to match with YNAB transaction
            ynab_match = self.match_to_ynab(txn, ynab_transactions)

            if ynab_match:
                print(f"    ✓ MATCHED YNAB Transaction:")
                print(f"      ID: {ynab_match.id}")
                print(f"      Payee: {ynab_match.payee_name}")
                print(f"      Amount: ${ynab_match.amount / 1000:.2f}")
                print(f"      Current Memo: {ynab_match.memo or '(empty)'}")
                print(f"      Approved: {'Yes' if ynab_match.approved else 'No'}")

                # Show what the new memo would be
                new_memo = self.format_memo(txn)
                print(f"      Proposed Memo: {new_memo}")

                # Update YNAB transaction memo (does not approve)
                update_success = False
                if self.dry_run:
                    print(f"      [DRY RUN] Would update YNAB transaction memo")
                    update_success = True  # Treat dry run as success for labeling purposes
                else:
                    if self.ynab_client.update_transaction_memo(ynab_match.id, new_memo, ynab_match):
                        print(f"      ✓ Updated YNAB transaction memo")
                        update_success = True
                    else:
                        print(f"      ✗ Failed to update YNAB transaction memo")

                matches.append({
                    'amazon': txn,
                    'ynab': ynab_match,
                    'new_memo': new_memo,
                    'update_success': update_success
                })
            else:
                print(f"    ✗ No matching YNAB transaction found")
                # Debug: Show potential matches
                amount_sign = '+' if is_return else '-'
                amount_display = f"{amount_sign}${txn['amount']:.2f}" if txn['amount'] is not None else "N/A"
                print(f"      Looking for: Date={txn['date'].date()} (±{self.date_buffer_days} days), Amount={amount_display}, Payee contains 'Amazon'")
                # Show YNAB transactions on same date
                same_date_txns = [t for t in ynab_transactions
                                 if datetime.strptime(str(t.date), '%Y-%m-%d').date() == txn['date'].date()]
                if same_date_txns:
                    print(f"      Found {len(same_date_txns)} YNAB transaction(s) on {txn['date'].date()}:")
                    for t in same_date_txns[:10]:  # Show up to 10
                        print(f"        - {t.payee_name}: ${t.amount/1000:.2f}")

            # Label email appropriately
            if self.dry_run:
                print(f"    [DRY RUN] Would mark email as processed")
                if ynab_match:
                    print(f"    [DRY RUN] Would mark email as matched")
            else:
                # Always mark as processed (we checked it)
                self.email_client.label_as_processed(txn['email_id'])
                print(f"    ✓ Marked email as processed")

                # Mark as matched only if YNAB was successfully updated
                if ynab_match and matches and matches[-1].get('update_success'):
                    self.email_client.label_as_matched(txn['email_id'])
                    print(f"    ✓ Marked email as matched")

            print()  # Empty line between transactions

        return matches
