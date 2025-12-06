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
        category_id: Optional[str] = None
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
                category_id=category_id
            )

            self.transactions_api.create_transaction(
                self.budget_id,
                transaction
            )
            print(f"Created transaction: {payee_name} - ${amount/1000:.2f}")
            return True
        except Exception as e:
            print(f"Error creating transaction: {e}")
            return False

    def update_transaction_category(
        self,
        transaction_id: str,
        category_id: str
    ) -> bool:
        """
        Update the category of an existing transaction

        Args:
            transaction_id: YNAB transaction ID
            category_id: YNAB category ID

        Returns:
            True if successful, False otherwise
        """
        try:
            transaction = TransactionRequest(category_id=category_id)
            self.transactions_api.update_transaction(
                self.budget_id,
                transaction_id,
                transaction
            )
            print(f"Updated transaction {transaction_id} category")
            return True
        except Exception as e:
            print(f"Error updating transaction: {e}")
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
