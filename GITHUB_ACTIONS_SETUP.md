# GitHub Actions Setup Guide

This guide will help you set up automated YNABify runs using GitHub Actions (free, no server needed).

## How It Works

- Runs automatically every 6 hours (4 times per day)
- Uses GitHub's free automation service
- Secrets are stored securely in GitHub
- Can also trigger manually from GitHub UI

## Setup Steps

### 1. Push the Workflow File

The workflow file is already created at `.github/workflows/sync-ynab.yml`. Just commit and push it:

```bash
git add .github/workflows/sync-ynab.yml
git commit -m "Add GitHub Actions workflow for automated YNAB sync"
git push
```

### 2. Add Secrets to GitHub

Go to your GitHub repository and add these secrets:

1. Navigate to: **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

2. Add each of these secrets (copy values from your `.env` file):

   | Secret Name | Value |
   |-------------|-------|
   | `YNAB_ACCESS_TOKEN` | Your YNAB personal access token |
   | `YNAB_BUDGET_ID` | Your YNAB budget ID |
   | `EMAIL_ADDRESS` | congchen5.ynabify@gmail.com |
   | `EMAIL_APP_PASSWORD` | Your Gmail app password |

**Important:** Never commit your `.env` file to GitHub. Secrets are the secure way to provide credentials.

### 3. Enable Actions (if needed)

- Go to the **Actions** tab in your GitHub repository
- If prompted, click **"I understand my workflows, go ahead and enable them"**

### 4. Verify It Works

**Manual test:**
1. Go to **Actions** tab
2. Click **"Sync YNAB Transactions"** workflow
3. Click **"Run workflow"** → **"Run workflow"**
4. Wait for it to complete and check the logs

**Check the schedule:**
- The workflow will run automatically every 6 hours
- Check the **Actions** tab to see run history

## Adjusting Frequency

Edit `.github/workflows/sync-ynab.yml` and change the cron schedule:

```yaml
schedule:
  # Every 6 hours (current setting)
  - cron: '0 */6 * * *'

  # Every hour (more responsive)
  - cron: '0 * * * *'

  # Every 12 hours (more conservative)
  - cron: '0 */12 * * *'

  # Every day at 9 AM and 9 PM UTC
  - cron: '0 9,21 * * *'
```

**Note:** Times are in UTC. Convert to your timezone when planning.

## Monitoring

- Check the **Actions** tab for run history
- Click on any run to see detailed logs
- You'll get email notifications if a run fails (configurable in GitHub settings)

## Free Tier Limits

GitHub Actions free tier:
- **Public repos**: Unlimited minutes
- **Private repos**: 2,000 minutes/month

Your usage (approximate):
- Each run: ~2 minutes
- Every 6 hours: 4 runs/day × 30 days = 120 runs/month
- Total: ~240 minutes/month (well within free tier)

## Troubleshooting

**Workflow not running:**
- Check that secrets are set correctly (go to Settings → Secrets and variables → Actions)
- Verify the workflow file is in the correct location: `.github/workflows/sync-ynab.yml`
- Make sure Actions are enabled (Actions tab)

**Run fails:**
- Click on the failed run in the Actions tab
- Expand the steps to see error messages
- Common issues:
  - Incorrect secrets (double-check values)
  - Gmail app password expired
  - YNAB token expired

**Want to disable:**
- Go to Actions tab → Select workflow → Click ⋯ (three dots) → Disable workflow
- Or delete the `.github/workflows/sync-ynab.yml` file

## Alternative: Local Cron Job

If you prefer running on your own computer (requires keeping it on):

**macOS/Linux:**
```bash
# Edit crontab
crontab -e

# Add this line (runs every 6 hours)
0 */6 * * * cd /path/to/YNABify && source venv/bin/activate && python main.py >> /path/to/logs/ynabify.log 2>&1
```

**Windows:**
Use Task Scheduler to run the script on a schedule.

---

**Recommendation:** Stick with GitHub Actions - it's simpler, more reliable, and doesn't require keeping your computer on.
