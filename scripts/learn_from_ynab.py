#!/usr/bin/env python3
"""
Learning System - Generate Category Rules from Approved YNAB Transactions

Analyzes approved YNAB transactions (categorized + cleared) and automatically
generates new keyword rules for category_rules.yaml. Uses frequency analysis
to find common patterns in payee names and memos.

Features:
- Only learns from approved transactions (user has reviewed)
- Checkpoint system for incremental learning (tracks last processed timestamp)
- Frequency analysis: finds keywords that appear 3+ times for a category
- Appends new rules (preserves existing manual rules)
- Marks learned rules with metadata (source: learned, learned_at: timestamp)

Usage:
    python scripts/learn_from_ynab.py [--dry-run] [--min-frequency MIN]

Options:
    --dry-run           Show what rules would be generated without updating YAML
    --min-frequency MIN Minimum keyword frequency (default: 3)
"""

import os
import sys
import yaml
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Set
import re

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ynab_client import YNABClient
from dotenv import load_dotenv


def load_config(config_path='category_rules.yaml'):
    """Load existing category rules configuration"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def save_config(config, config_path='category_rules.yaml'):
    """Save updated configuration to YAML file"""
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False


def extract_keywords(texts: List[str], min_frequency: int = 3) -> List[str]:
    """
    Extract common keywords from list of text strings using frequency analysis

    Args:
        texts: List of payee/memo text strings
        min_frequency: Minimum times a keyword must appear to be included

    Returns:
        List of keywords sorted by frequency (most common first)
    """
    # Stop words to filter out
    stop_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'a', 'an', 'this', 'that', 'these', 'those', 'is', 'was', 'are', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'can', 'from', 'by', 'as',
        'payment', 'purchase', 'transaction', 'order', 'transfer', 'deposit',
        'amazon', 'link', 'http', 'https', 'www', 'com', 'net', 'org',
        'return', 'refund'
    }

    # Extract words from all texts
    word_freq = defaultdict(int)
    for text in texts:
        if not text:
            continue
        # Convert to lowercase and extract words
        text_lower = text.lower()
        # Remove URLs
        text_lower = re.sub(r'https?://[^\s]+', '', text_lower)
        # Extract words (alphanumeric sequences)
        words = re.findall(r'\b[a-z][a-z0-9]*\b', text_lower)

        # Count unique words per text (not total occurrences)
        unique_words = set(words)
        for word in unique_words:
            # Filter stop words and very short words
            if word not in stop_words and len(word) > 2:
                word_freq[word] += 1

    # Filter by minimum frequency and sort by frequency
    keywords = [
        word for word, freq in word_freq.items()
        if freq >= min_frequency
    ]

    # Sort by frequency (most common first) and limit to top 10
    keywords.sort(key=lambda w: word_freq[w], reverse=True)
    return keywords[:10]


def learn_from_approved_transactions(
    ynab_client: YNABClient,
    config: Dict,
    min_frequency: int = 3,
    dry_run: bool = False,
    config_path: str = 'category_rules.yaml'
) -> List[Dict]:
    """
    Analyze approved transactions and generate new category rules

    Args:
        ynab_client: YNABClient instance
        config: Current configuration dict
        min_frequency: Minimum keyword frequency
        dry_run: If True, don't update config file
        config_path: Path to configuration file (default: 'category_rules.yaml')

    Returns:
        List of new rules generated
    """
    print("\n=== Learning from Approved YNAB Transactions ===\n")

    # Get checkpoint timestamp
    last_checkpoint = config.get('learning', {}).get('last_checkpoint')
    if last_checkpoint:
        since_date = last_checkpoint[:10]  # Extract YYYY-MM-DD from ISO timestamp
        print(f"Incremental learning since last checkpoint: {last_checkpoint}")
    else:
        # First run: learn from last 90 days
        since_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
        print(f"First run: learning from last 90 days (since {since_date})")

    # Fetch transactions
    print(f"\n📥 Fetching approved transactions since {since_date}...")
    transactions = ynab_client.get_transactions(since_date=since_date)

    # Filter to approved transactions with categories
    approved_txns = [
        txn for txn in transactions
        if txn.approved and txn.category_id
    ]

    print(f"Found {len(approved_txns)} approved & categorized transactions")

    if len(approved_txns) == 0:
        print("\n⚠ No approved transactions found. Nothing to learn.")
        return []

    # Group transactions by category
    category_patterns = defaultdict(list)
    category_names = {}  # Map category_id -> name

    for txn in approved_txns:
        category_name = txn.category_name
        if not category_name:
            continue

        category_names[txn.category_id] = category_name

        # Extract text for pattern analysis (payee + memo)
        text = f"{txn.payee_name or ''} {txn.memo or ''}".strip()
        if text:
            category_patterns[category_name].append(text)

    print(f"\n🔍 Analyzing {len(category_patterns)} unique categories...\n")

    # Extract keywords for each category
    new_rules = []
    for category_name, texts in category_patterns.items():
        if len(texts) < min_frequency:
            # Not enough data for this category
            continue

        keywords = extract_keywords(texts, min_frequency=min_frequency)

        if len(keywords) > 0:
            print(f"📝 {category_name} ({len(texts)} transactions)")
            print(f"   Keywords: {', '.join(keywords)}")

            new_rules.append({
                'category': category_name,
                'keywords': keywords,
                'confidence': 0.85,  # Learned rules have medium confidence
                'source': 'learned',
                'learned_at': datetime.now().isoformat(),
                'sample_count': len(texts)
            })

    print(f"\n✓ Generated {len(new_rules)} new rules")

    if dry_run:
        print("\n⚠️  DRY RUN MODE - Rules not saved")
        return new_rules

    # Append new rules to config (preserve existing)
    if 'rules' not in config:
        config['rules'] = []

    # Check for duplicates (same category + similar keywords)
    existing_categories = {rule.get('category') for rule in config['rules']}
    rules_to_add = []

    for rule in new_rules:
        if rule['category'] in existing_categories:
            print(f"⚠ Skipping {rule['category']} - already has rules")
        else:
            rules_to_add.append(rule)

    if rules_to_add:
        config['rules'].extend(rules_to_add)
        print(f"\n✓ Added {len(rules_to_add)} new rules to configuration")

    # Update checkpoint
    if 'learning' not in config:
        config['learning'] = {}
    config['learning']['last_checkpoint'] = datetime.now().isoformat()
    config['learning']['enabled'] = True

    # Save updated configuration
    if save_config(config, config_path):
        print(f"✓ Updated {config_path}")
        print(f"✓ Checkpoint updated: {config['learning']['last_checkpoint']}")
    else:
        print("✗ Failed to save configuration")

    return rules_to_add


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Learn category rules from approved YNAB transactions')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be learned without updating config')
    parser.add_argument('--min-frequency', type=int, default=3, help='Minimum keyword frequency (default: 3)')
    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Check required environment variables
    ynab_token = os.getenv('YNAB_ACCESS_TOKEN')
    budget_id = os.getenv('YNAB_BUDGET_ID')

    if not ynab_token or not budget_id:
        print("Error: Missing YNAB_ACCESS_TOKEN or YNAB_BUDGET_ID in .env file")
        return

    # Initialize YNAB client
    ynab_client = YNABClient(ynab_token, budget_id)

    # Test connection
    print("=== Testing YNAB Connection ===\n")
    if not ynab_client.test_connection():
        print("✗ Failed to connect to YNAB")
        return
    print("✓ Connected to YNAB")

    # Load current configuration
    config_path = 'category_rules.yaml'
    config = load_config(config_path)

    # Run learning
    new_rules = learn_from_approved_transactions(
        ynab_client=ynab_client,
        config=config,
        min_frequency=args.min_frequency,
        dry_run=args.dry_run,
        config_path=config_path
    )

    # Print summary
    print("\n" + "=" * 80)
    print("=== LEARNING SUMMARY ===")
    if args.dry_run:
        print("=== ⚠️  DRY RUN MODE - No changes were made ===")
    print("=" * 80)

    print(f"\n📊 New Rules Generated: {len(new_rules)}")

    if new_rules:
        print("\n🎓 Learned Categories:")
        for rule in new_rules:
            print(f"  - {rule['category']} ({rule['sample_count']} transactions, {len(rule['keywords'])} keywords)")

    if not args.dry_run and new_rules:
        print(f"\n✓ Configuration updated with {len(new_rules)} new rules")
        print(f"✓ Run bulk categorization to apply new rules to existing transactions")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
