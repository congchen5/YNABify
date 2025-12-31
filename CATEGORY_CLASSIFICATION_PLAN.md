# Plan: Add Automatic Category Classification

## Overview

Add intelligent category classification to YNABify using a **hybrid approach** (rule-based + LLM fallback) that is **conservative** (only sets category when confident ≥75%) and handles **multi-item orders** using the most prominent item.

## User Requirements (Confirmed)
- ✅ Hybrid: Keyword rules first, Claude Haiku LLM for unknowns (~$2-3/month)
- ✅ Conservative: Leave uncategorized if uncertain (<75% confidence)
- ✅ Multi-item: Use highest-price/most prominent item for categorization
- ✅ Manual approval: User still reviews all transactions in YNAB
- ✅ Works for both Amazon and Venmo transactions
- ✅ Generic rules across all platforms (not platform-specific)
- ✅ Bulk categorization of ALL existing YNAB transactions
- ✅ Learning system to generate rules from approved transactions

## Architecture

### New Components

**1. CategoryClassifier (`category_classifier.py`)** - NEW MODULE

Core classification engine with methods for Amazon, Venmo, and generic transactions.

**2. Category Rules Config (`category_rules.yaml`)** - NEW FILE

**IMPORTANT**:
- Rules are **generic across all platforms** (Amazon, Venmo, etc.)
- Category names MUST match EXACTLY what exists in your YNAB budget
- Run `ynab_client.get_categories()` first to see available categories
- A keyword like "baby wipes" should match to "Luca Consumables" regardless of source

## Implementation Steps

### Phase 1: Foundation (Rules-Based Only)

**Step 1.1: Create CategoryClassifier Module**
- File: `category_classifier.py`
- Implement class structure with classification methods
- Implement rule-based matching only (no LLM yet)
- Implement YNAB category caching and name-to-ID mapping

**Step 1.2: Fetch YNAB Categories**
- Use `ynab_client.get_categories()` to fetch all available categories
- Display category names and IDs for user reference
- This ensures we only create rules for categories that actually exist in YNAB

**Step 1.3: Create Category Rules Config**
- File: `category_rules.yaml`
- Add 10-15 starter rules based on ACTUAL YNAB categories from Step 1.2
- NOTE: Category names MUST match exactly what's in YNAB

**Step 1.4: Update Dependencies**
- Add `pyyaml` to `requirements.txt`
- Run `pip install pyyaml` locally

**Step 1.5: Test CategoryClassifier Standalone**
- Test rule matching and category mapping

### Phase 2: Integration (Amazon & Venmo)

**Step 2.1: Integrate with Amazon**
- Modify `amazon_integration.py` to add classifier parameter and classification logic

**Step 2.2: Integrate with Venmo**
- Modify `venmo_integration.py` to add classifier parameter and classification logic

**Step 2.3: Initialize in Main**
- Modify `main.py` to initialize and pass classifier to integrations

**Step 2.4: Test End-to-End (DRY_RUN Mode)**
- Test with real Amazon and Venmo emails

### Phase 3: LLM Enhancement (Optional but Recommended)

**Step 3.1: Install Anthropic SDK**
**Step 3.2: Implement LLM Fallback**
**Step 3.3: Add Environment Variables**
**Step 3.4: Test LLM Fallback**

### Phase 4: Logging & Monitoring

**Step 4.1: Add Uncertain Item Logging**
**Step 4.2: Add .gitignore Entry**
**Step 4.3: Add Classification Stats**

### Phase 5: Testing & Deployment

**Step 5.1: Local Testing (Full Workflow)**
**Step 5.2: Deploy to GitHub Actions**
**Step 5.3: Monitor First Week**

### Phase 6: Bulk Categorization (Existing YNAB Transactions)

**Step 6.1: Create Bulk Categorization Script**
- File: `scripts/bulk_categorize.py`
- Apply category classification to ALL existing YNAB transactions across all accounts

**IMPORTANT**: Process ALL transactions by default, even if they already have a category. YNAB's auto-categorization is often wrong.

**Step 6.2: Implement Bulk Classification Logic**
- Default: process all transactions (skip_categorized=False)
- Track: updated, newly_classified, no_match

**Step 6.3: Test Bulk Categorization**
- Test on small date ranges first with DRY_RUN

### Phase 7: Learning System (Learn from Approved Transactions)

**Step 7.1: Define "Approved" Transaction Criteria**
- Approved = has category set + is cleared/approved in YNAB
- Store checkpoint timestamp for incremental learning

**Step 7.2: Create Learning Script**
- File: `scripts/learn_from_ynab.py`
- Analyze approved transactions and generate rules

**Step 7.3: Implement Learning Logic**
- Frequency analysis to extract keywords
- Append new rules (preserve existing)

**Step 7.4: Keyword Extraction Strategy**
**Step 7.5: Rule Preservation Strategy**
**Step 7.6: Test Learning System**

### Phase 8: Documentation

**Step 8.1: Update CLAUDE.md**
**Step 8.2: Update SETUP.md**
**Step 8.3: Update README.md**

## Key Design Decisions

**Generic Rules Across Platforms:**
- Rules are platform-agnostic: same keywords work for Amazon, Venmo, or any future source
- Example: "baby wipes" → "Luca Consumables" works whether from Amazon order or Venmo payment
- Simplifies maintenance: one rule set instead of multiple platform-specific sets

**Bulk Categorization:**
- Default behavior: overwrite all categories (YNAB auto-categorization is often wrong)
- Use skip_categorized=True flag only if you trust existing categories

**Learning System:**
- Checkpoint system prevents reprocessing same transactions
- Learned rules marked with metadata for easy identification

See full plan for complete details.
