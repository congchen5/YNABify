# Setup Guide

## Step 1: Create Dedicated Email Account

1. Create a new Gmail account (e.g., `yourname.ynabbot@gmail.com`)
2. Enable 2-Step Verification:
   - Go to Google Account → Security → 2-Step Verification
   - Follow the setup process
3. Generate App Password:
   - Go to Google Account → Security → App passwords
   - Select "Mail" and "Other (custom name)"
   - Name it "YNAB Bot"
   - Copy the 16-character password (save for later)

## Step 2: Set Up Email Forwarding

In your **main** Gmail account:
1. Go to Settings → See all settings → Forwarding and POP/IMAP
2. Click "Add a forwarding address"
3. Enter your new bot email address
4. Confirm the forwarding request in the bot email
5. Create filters for transaction emails:

   **For Venmo:**
   - Search: `from:venmo@venmo.com`
   - Click "Create filter"
   - Check "Forward it to" and select your bot email
   - Click "Create filter"

   **For Amazon:**
   - Search: `from:auto-confirm@amazon.com`
   - Click "Create filter"
   - Check "Forward it to" and select your bot email
   - Click "Create filter"

## Step 3: Get YNAB Credentials

1. Go to https://app.youneedabudget.com/settings/developer
2. Click "New Token"
3. Copy your Personal Access Token
4. Open YNAB and note your Budget ID from the URL:
   - URL format: `https://app.youneedabudget.com/[BUDGET_ID]/budget`

## Step 4: Create .env File

```bash
cp .env.example .env
chmod 600 .env  # Restrict permissions
```

Edit `.env` and fill in all the values you collected above.

## Step 5: Install Dependencies

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 6: Run the Bot

```bash
python main.py
```

## Security Notes

- Never commit `.env` to git (already in `.gitignore`)
- The bot uses email parsing - no cookies or browser automation required
- You can revoke the YNAB token anytime from the YNAB settings
- You can revoke the Gmail app password anytime from Google Account settings
- The dedicated email account only receives transaction emails (security isolation)
