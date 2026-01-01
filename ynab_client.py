"""
YNAB API Client
Handles all interactions with the YNAB API
"""

from ynab_sdk import YNAB
from ynab_sdk.api.models.requests.transaction import TransactionRequest
from typing import List, Optional
import os


class YNABClient:
    def __init__(self, access_token: str, budget_id: str):
        """
        Initialize YNAB client

        Args:
            access_token: YNAB personal access token
            budget_id: YNAB budget ID
        """
        self.client = YNAB(access_token)
        self.budget_id = budget_id
        self.transactions_api = self.client.transactions
        self.categories_api = self.client.categories
        self.accounts_api = self.client.accounts

    def get_transactions(self, since_date: Optional[str] = None) -> List:
        """
        Get transactions from YNAB

        Args:
            since_date: Optional date string (YYYY-MM-DD) to get transactions since

        Returns:
            List of transaction objects
        """
        try:
            response = self.transactions_api.get_transactions(self.budget_id)
            transactions = response.data.transactions

            # Filter by date if provided
            if since_date:
                from datetime import datetime
                cutoff_date = datetime.strptime(since_date, '%Y-%m-%d').date()
                transactions = [
                    t for t in transactions
                    if datetime.strptime(str(t.date), '%Y-%m-%d').date() >= cutoff_date
                ]

            return transactions
        except Exception as e:
            print(f"Error fetching transactions: {e}")
            return []

    def get_uncategorized_transactions(self) -> List:
        """
        Get all uncategorized transactions

        Returns:
            List of uncategorized transactions
        """
        transactions = self.get_transactions()
        return [t for t in transactions if not t.category_id]

    def create_transaction(
        self,
        account_id: str,
        date: str,
        amount: int,  # In milliunits (e.g., $10.00 = 10000)
        payee_name: str,
        memo: Optional[str] = None,
        category_id: Optional[str] = None,
        cleared: Optional[str] = None
    ) -> bool:
        """
        Create a new transaction in YNAB

        Args:
            account_id: YNAB account ID
            date: Date in YYYY-MM-DD format
            amount: Amount in milliunits (e.g., $10.00 = 10000)
            payee_name: Name of the payee
            memo: Optional memo/note
            category_id: Optional category ID
            cleared: Optional cleared status ('cleared', 'uncleared', 'reconciled')

        Returns:
            True if successful, False otherwise
        """
        try:
            transaction = TransactionRequest(
                account_id=account_id,
                date=date,
                amount=amount,
                payee_name=payee_name,
                memo=memo,
                category_id=category_id,
                cleared=cleared
            )

            result = self.transactions_api.create_transactions(
                self.budget_id,
                [transaction]
            )
            print(f"Created transaction: {payee_name} - ${amount/1000:.2f}")
            return True
        except Exception as e:
            print(f"Error creating transaction: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_transaction_category(
        self,
        transaction_id: str,
        category_id: str,
        existing_transaction=None
    ) -> bool:
        """
        Update the category of an existing transaction

        Args:
            transaction_id: YNAB transaction ID
            category_id: YNAB category ID
            existing_transaction: The existing YNAB transaction object (optional, will fetch if not provided)

        Returns:
            True if successful, False otherwise
        """
        try:
            # If we don't have the transaction object, fetch it
            if existing_transaction is None:
                result = self.transactions_api.get_transaction_by_id(
                    self.budget_id,
                    transaction_id
                )
                existing_transaction = result.data.transaction

            # Create transaction request with ALL existing data plus new category
            transaction = TransactionRequest(
                account_id=existing_transaction.account_id,
                date=str(existing_transaction.date),
                amount=existing_transaction.amount,
                payee_id=existing_transaction.payee_id,
                payee_name=existing_transaction.payee_name,
                category_id=category_id,
                memo=existing_transaction.memo,
                cleared=existing_transaction.cleared,
                approved=existing_transaction.approved,
                flag_color=existing_transaction.flag_color,
                import_id=existing_transaction.import_id
            )

            self.transactions_api.update_transaction(
                self.budget_id,
                transaction_id,
                transaction
            )
            return True
        except Exception as e:
            print(f"Error updating transaction: {e}")
            return False

    def update_transaction_memo(
        self,
        transaction_id: str,
        memo: str,
        existing_transaction
    ) -> bool:
        """
        Update the memo of an existing transaction (does not approve)

        Args:
            transaction_id: YNAB transaction ID
            memo: Memo text to set
            existing_transaction: The existing YNAB transaction object

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"      DEBUG: Updating transaction {transaction_id}")
            print(f"      DEBUG: New memo: {memo}")
            print(f"      DEBUG: Existing approved: {existing_transaction.approved}")

            # Create transaction request with ALL existing data plus new memo
            transaction = TransactionRequest(
                account_id=existing_transaction.account_id,
                date=str(existing_transaction.date),
                amount=existing_transaction.amount,
                payee_id=existing_transaction.payee_id,
                payee_name=existing_transaction.payee_name,
                category_id=existing_transaction.category_id,
                memo=memo,
                cleared=existing_transaction.cleared,
                approved=existing_transaction.approved,
                flag_color=existing_transaction.flag_color,
                import_id=existing_transaction.import_id
            )

            result = self.transactions_api.update_transaction(
                self.budget_id,
                transaction_id,
                transaction
            )
            print(f"      DEBUG: API response: {result}")
            return True
        except Exception as e:
            print(f"Error updating transaction memo: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_categories(self) -> List:
        """
        Get all budget categories

        Returns:
            List of category objects
        """
        try:
            response = self.categories_api.get_categories(self.budget_id)
            return response.data.category_groups
        except Exception as e:
            print(f"Error fetching categories: {e}")
            return []

    def get_accounts(self) -> List:
        """
        Get all budget accounts

        Returns:
            List of account objects
        """
        try:
            response = self.accounts_api.get_accounts(self.budget_id)
            return response.data.accounts
        except Exception as e:
            print(f"Error fetching accounts: {e}")
            return []

    def test_connection(self) -> bool:
        """
        Test the connection to YNAB API

        Returns:
            True if connection successful, False otherwise
        """
        try:
            accounts = self.get_accounts()
            if accounts:
                print(f"✓ Connected to YNAB successfully")
                print(f"  Found {len(accounts)} account(s)")
                return True
            return False
        except Exception as e:
            print(f"✗ Failed to connect to YNAB: {e}")
            return False
