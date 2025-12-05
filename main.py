#!/usr/bin/env python3
"""
YNABify - YNAB Budget Bot
Helps categorize Amazon and Venmo transactions
"""

import os
from dotenv import load_dotenv

def main():
    # Load environment variables
    load_dotenv()

    ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
    budget_id = os.getenv('YNAB_BUDGET_ID')

    if not ynab_token or not budget_id:
        print("Error: Missing YNAB credentials in .env file")
        return

    print("YNABify started successfully!")
    print(f"Connected to budget: {budget_id}")

    # TODO: Add bot functionality here

if __name__ == "__main__":
    main()
