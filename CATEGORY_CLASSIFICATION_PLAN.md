# Plan: Add Automatic Category Classification

## Overview

Add intelligent category classification using **hybrid approach** (rule-based + LLM fallback) that is **conservative** (only sets category when confident) and handles **multi-item orders** using highest-price item.

## User Requirements (Confirmed)
- ✅ Hybrid: Rules first, Claude Haiku for unknowns (~$2-3/month)
- ✅ Conservative: Leave uncategorized if uncertain (<75% confidence)
- ✅ Multi-item: Use highest-price item for categorization
- ✅ Manual approval: User still reviews all transactions in YNAB

## Architecture

### New Components

**1. CategoryClassifier (`category_classifier.py`)** - NEW MODULE
- Core classification engine with two methods:
  - `classify_amazon_transaction(transaction)` → category or None
  - `classify_venmo_transaction(transaction)` → category or None
- Rule-based matching (keyword patterns in YAML)
- LLM fallback (Anthropic Claude Haiku)
- Confidence scoring and thresholding
- Category name → YNAB ID mapping with fuzzy matching

**2. Category Rules (`category_rules.yaml`)** - NEW CONFIG FILE
```yaml
rules:
  amazon_items:
    - category: "Groceries"
      keywords: ["food", "snack", "coffee", "protein bar"]
      confidence: 0.95
    - category: "Electronics"
      keywords: ["cable", "charger", "usb", "hdmi"]
      confidence: 0.9
  venmo_payees:
    - category: "Dining Out"
      keywords: ["restaurant", "cafe", "pizza"]
      confidence: 0.9

llm:
  provider: "anthropic"
  model: "claude-3-haiku-20240307"
  confidence_threshold: 0.8

conservative:
  minimum_confidence: 0.75
  skip_on_uncertainty: true
```

### Integration Points

**Amazon Integration** (`amazon_integration.py:485`)
- After memo update succeeds
- Add classification call
- Update category if confident
- Respect DRY_RUN mode

**Venmo Integration** (`venmo_integration.py:268-276`)
- Before transaction creation
- Get category from classifier
- Pass to `create_transaction()` instead of None

**Main** (`main.py:128+`)
- Initialize CategoryClassifier with YNAB client
- Pass classifier to both integrations
- Add classification stats to summary

## Implementation Steps

### Phase 1: Foundation
1. Create `category_classifier.py` with class structure
2. Implement rule-based matching (keyword search)
3. Implement YNAB category fetching/caching
4. Create `category_rules.yaml` with 10-15 starter rules
5. Add `pyyaml` to requirements.txt

### Phase 2: Integration
6. Modify `amazon_integration.py`:
   - Add `category_classifier` param to `__init__` (line 13)
   - After line 485, add classification logic
7. Modify `venmo_integration.py`:
   - Add `category_classifier` param to `__init__` (line 12)
   - Before line 269, get category from classifier
8. Modify `main.py`:
   - Add CategoryClassifier import (line 9)
   - Initialize classifier (after line 128)
   - Pass to integrations
   - Add stats to summary (after line 195)

### Phase 3: LLM Enhancement
9. Install `anthropic` package
10. Implement `_classify_with_llm()` method
11. Add error handling for API failures
12. Add `ANTHROPIC_API_KEY` to `.env` and GitHub Secrets
13. Update `.github/workflows/sync-ynab.yml` with new env var

### Phase 4: Testing & Deployment
14. Test locally with DRY_RUN=True
15. Trigger manual GitHub Actions run
16. Monitor logs and verify categories in YNAB
17. Update documentation (CLAUDE.md, SETUP.md, README.md)

## Classification Logic Flow

```
Transaction arrives
    ↓
Try rule-based matching
    ├─ Match found (confidence >= 0.75)
    │   └─ Return category
    └─ No match or low confidence
        ↓
    Try LLM fallback (if API key set)
        ├─ LLM confident (>= 0.8)
        │   └─ Return category
        └─ LLM uncertain or failed
            └─ Return None (leave uncategorized)
```

## Key Design Decisions

**Why Claude Haiku?**
- Cheapest Claude model ($0.25/$1.25 per million tokens)
- Fast enough for batch processing (~1-2 sec)
- Excellent at structured categorization tasks
- Cost: ~$0.0001 per call = ~$1-3/month total

**Multi-Item Handling:**
- Use `item_name_from_subject` (extracted from email subject, usually most prominent)
- Fallback to first item in `items[]` array
- Note: Amazon emails don't always include per-item prices, so "highest price" = "most prominent"

**Conservative Approach:**
- Minimum confidence threshold: 0.75 (adjustable in config)
- Log uncertain items to `classification_uncertain.log` (gitignored)
- Review monthly to build better rules

**Error Handling:**
- LLM API down → skip classification, don't fail run
- Category not found → leave uncategorized
- Invalid rules file → disable classification gracefully
- Never fail entire run due to classification issues

## Environment Variables

**Add to `.env`:**
```
ANTHROPIC_API_KEY=your_key_here
```

**Add to GitHub Secrets:**
- Name: `ANTHROPIC_API_KEY`
- Value: Get from https://console.anthropic.com/

**Update workflow** (`.github/workflows/sync-ynab.yml`):
```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Success Metrics

**After 1 week:**
- 70%+ of transactions automatically categorized
- <5% incorrect categories
- <$0.50 LLM usage

**After 1 month:**
- 85%+ coverage
- 20+ rules added from uncertain log
- 80%+ reduction in manual categorization work

## Maintenance Plan

**Weekly:**
- Review `classification_uncertain.log`
- Identify common patterns
- Add new keywords to `category_rules.yaml`

**Monthly:**
- Check LLM usage and costs in logs
- Adjust confidence thresholds if needed
- Update documentation with new rules

## Critical Files

**New Files:**
- `category_classifier.py` - Classification engine
- `category_rules.yaml` - Keyword rules and config
- `classification_uncertain.log` - Logged uncertain items (gitignored)
- `test_category_classifier.py` - Unit tests

**Modified Files:**
- `amazon_integration.py` (lines 13, 485+) - Add classifier
- `venmo_integration.py` (lines 12, 268-276) - Add classifier
- `main.py` (lines 9, 128+, 195+) - Initialize & integrate
- `.env.example` - Document ANTHROPIC_API_KEY
- `.github/workflows/sync-ynab.yml` - Add env var
- `requirements.txt` - Add anthropic, pyyaml
- `.gitignore` - Add classification_uncertain.log

**Unchanged (Used, Not Modified):**
- `ynab_client.py` (lines 110-136, 188-200) - Existing category methods
