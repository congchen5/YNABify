# Claude Code Instructions for YNABify

## General Guidelines

### Code Execution
- **Always show all print statements and output** when running code. Never suppress or summarize console output.
- Show full command output including debug statements, status messages, and results.

### Project Context
- This is a Python project that automates YNAB transaction updates by parsing emails from vendors (Amazon, Venmo, etc.)
- **Email Account**: When the user refers to "email", they mean congchen5.ynabify@gmail.com
- The main entry point is `main.py`
- Configuration is in `.env` file
- Key modules:
  - `amazon_integration.py`: Processes Amazon order emails and matches to YNAB transactions
  - `venmo_integration.py`: Processes Venmo transaction emails
  - `email_client.py`: Handles Gmail IMAP connections
  - `ynab_client.py`: Handles YNAB API interactions

### Running the Project
- Use virtual environment: `source venv/bin/activate`
- Run with: `python main.py`
- Configuration flags in `main.py`:
  - `DEBUG_TRANSACTION_LIMIT`: Number of emails to process (for testing)
  - `DATE_BUFFER_DAYS`: Days +/- to match transactions
  - `DRY_RUN`: When True, no modifications are made (no email labels, no YNAB updates)
