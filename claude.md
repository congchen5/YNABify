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
  - `EMAIL_DAYS_BACK`: Only process emails from last N days (default: 60)
  - `DRY_RUN`: When True, no modifications are made (no email labels, no YNAB updates)

---

## Comprehensive Project Context

### Project Overview
YNABify is an automation tool that syncs transaction details from email receipts (Amazon, Venmo) to YNAB budget transactions. It:
- Connects to Gmail via IMAP to fetch order/payment emails
- Parses email content to extract transaction details
- Matches emails to existing YNAB transactions or creates new ones
- Updates YNAB with detailed item-level information
- Labels emails to track processing status

### Architecture & Core Components

**Email Processing Flow:**
```
main.py
  → email_processor.py (central coordinator)
    → email_client.py (Gmail IMAP)
    → amazon_integration.py (parse & match Amazon)
    → venmo_integration.py (parse & create Venmo)
    → ynab_client.py (YNAB API)
```

**Key Files:**
- `main.py`: Entry point, configuration, connection testing
- `email_processor.py`: Central email processing loop, routes emails to integrations
- `amazon_integration.py`: Amazon email parsing, YNAB transaction matching, memo updates
- `venmo_integration.py`: Venmo email parsing, YNAB transaction creation
- `email_client.py`: Gmail IMAP connection, email fetching, labeling
- `ynab_client.py`: YNAB API wrapper (accounts, transactions, categories, updates)

### Success-Only Label System with Automatic Retry

The project uses a simple, success-based label system with automatic retry:

**Labels:**
1. **`matched`** (Amazon only): Applied after successfully updating YNAB transaction
   - Indicates email was matched to YNAB transaction and memo was updated
   - Once labeled, email is permanently skipped

2. **`created`** (Venmo only): Applied after successfully creating YNAB transaction
   - Indicates YNAB transaction was created for this Venmo payment
   - Once labeled, email is permanently skipped

**Automatic Retry Behavior:**
- Emails without success labels are retried on every run
- Date filtering (EMAIL_DAYS_BACK=60) prevents scanning old emails
- Solves timing issue where Amazon emails arrive before YNAB syncs transactions
- No manual reprocessing needed - system automatically retries until success

**Why This Works:**
- Amazon emails keep retrying until YNAB transaction appears and gets matched
- Venmo emails keep retrying if creation fails (network issues, etc.)
- Once successful, emails are skipped forever via success labels
- Old emails (>60 days) are automatically ignored

### Amazon Integration Details

**Email Parsing:**
- Parses Amazon order confirmation emails from `ship-confirm@amazon.com`
- Extracts: order total, order date, order ID, and individual items
- Handles multi-order emails (e.g., "Your 2 Amazon.com orders have shipped")
- Item extraction includes: name, quantity, price, product links

**Date Parsing:**
- Uses `.rsplit(',', 1)[-1].strip()` to handle complex date formats like "Monday, December 16, 2024"
- Configurable `DATE_BUFFER_DAYS` (default: 5) for fuzzy date matching

**YNAB Matching:**
- Matches Amazon emails to YNAB transactions using:
  - Payee contains "Amazon" or category is Amazon
  - Amount matches order total (considers negative sign)
  - Date within buffer range
  - Not already matched (no 'matched' label)

**Memo Updates:**
- Updates YNAB transaction memo with item details
- Format: `[Item] x [Qty] ($[Price]): [Link] | ...`
- Preserves existing `...` truncation indicator if memo was already truncated
- Applies `matched` label only after successful update
- Emails without label automatically retry on next run until matched

### Venmo Integration Details

**Email Parsing:**
- Parses Venmo transaction notification emails from `venmo@venmo.com`
- Extracts: amount, sender/recipient, note, transaction date

**YNAB Transaction Creation:**
- Creates new transactions in default Venmo account
- Transaction details populated from email data
- Applies `created` label only after successful creation
- Emails without label automatically retry on next run until created
- Duplicate detection prevents creating same transaction twice

### Configuration Options

**Environment Variables (`.env`):**
- `YNAB_ACCESS_TOKEN`: YNAB API personal access token
- `YNAB_BUDGET_ID`: Target YNAB budget ID
- `EMAIL_ADDRESS`: Gmail address (congchen5.ynabify@gmail.com)
- `EMAIL_APP_PASSWORD`: Gmail app password
- `EMAIL_IMAP_SERVER`: IMAP server (default: imap.gmail.com)
- `EMAIL_IMAP_PORT`: IMAP port (default: 993)

**Main.py Flags:**
- `DEBUG_TRANSACTION_LIMIT`: Max emails to process (default: 1000)
- `DATE_BUFFER_DAYS`: Date matching tolerance (default: 5 days)
- `EMAIL_DAYS_BACK`: Only process emails from last N days (default: 60)
- `DRY_RUN`: Run without modifications (default: False)

### Technical Patterns & Best Practices

**Date Parsing:**
- Always use `.rsplit(',', 1)[-1].strip()` for complex date strings
- Handle timezone-aware and naive datetime objects carefully

**Multi-Order Parsing:**
- Detect multi-order emails with regex patterns
- Parse multiple order blocks within single email
- Process each order independently

**DRY Principle:**
- Email parsing logic only in integration classes (amazon_integration, venmo_integration)
- email_processor.py only coordinates and routes
- No duplication of parsing logic

**Error Handling:**
- Integration methods return structured data or None
- Central processor aggregates results and generates statistics
- Graceful handling of missing/malformed email data

### File Structure
```
YNABify/
├── main.py                    # Entry point
├── email_processor.py         # Central coordinator
├── amazon_integration.py      # Amazon-specific logic
├── venmo_integration.py       # Venmo-specific logic
├── email_client.py           # Gmail IMAP client
├── ynab_client.py            # YNAB API wrapper
├── scripts/                   # Utility scripts
│   ├── analyze_return_emails.py
│   ├── list_labels.py
│   ├── README.md
│   └── fix_venmo_duplicates.py
├── .env                       # Configuration (gitignored)
├── .env.example              # Configuration template
├── SETUP.md                  # Setup instructions
├── CLAUDE.md                 # This file
└── README.md                 # Project overview
```

### Common Operations

**Running the bot:**
```bash
source venv/bin/activate
python main.py
```

**Testing without modifications:**
```bash
# Set DRY_RUN = True in main.py
python main.py
```

**Analyzing email labels:**
```bash
python scripts/list_labels.py
```

**Analyzing return emails:**
```bash
python scripts/analyze_return_emails.py
```

**Note on reprocessing:**
- No manual reprocessing needed - emails automatically retry until successful
- System only processes emails from last 60 days (configurable via EMAIL_DAYS_BACK)

### Recent Major Work

1. **Success-Only Label System with Automatic Retry**:
   - Removed `processed` label entirely
   - Only use success labels: `matched` (Amazon) and `created` (Venmo)
   - Added date-based filtering (EMAIL_DAYS_BACK=60)
   - Automatic retry until success - solves timing issues
   - No manual reprocessing needed

2. **Memo Truncation Preservation**:
   - Preserves `...` indicator when updating memos
   - Maintains visibility of truncation state

3. **DRY_RUN Mode**:
   - Safe testing mode that makes no modifications
   - No email labeling, no YNAB updates

4. **Scripts Organization**:
   - Created scripts/ folder with utilities
   - Comprehensive README for each script

5. **Documentation**:
   - Added email account context (congchen5.ynabify@gmail.com)
   - Comprehensive SETUP.md guide
   - Script documentation

### Known Patterns & Gotchas

**Email Labeling:**
- Only apply success labels: `matched` (Amazon) or `created` (Venmo)
- Never label emails that haven't completed successfully
- Label operations must be in email_client.py, not integrations
- Emails without labels will automatically retry on next run

**Date Matching:**
- YNAB dates are in YYYY-MM-DD format
- Amazon emails have complex formats - use rsplit pattern
- DATE_BUFFER_DAYS accounts for processing delays

**Multi-Order Emails:**
- Amazon can send single email for multiple orders
- Must parse and process each order independently
- Each order matches to separate YNAB transaction

**Memo Format:**
- YNAB memo field has character limits
- Use truncation indicator `...` when needed
- Preserve existing truncation when updating
