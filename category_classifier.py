"""
Category Classifier - Classify transactions using rules and LLM fallback
"""

import os
import re
import yaml
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher


# Optional LLM support (only imported if ANTHROPIC_API_KEY is set)
try:
    from anthropic import Anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class CategoryClassifier:
    def __init__(self, ynab_client, config_path='category_rules.yaml'):
        """
        Initialize category classifier

        Args:
            ynab_client: YNABClient instance
            config_path: Path to category rules YAML file
        """
        self.ynab_client = ynab_client
        self.config_path = config_path
        self.rules = self._load_rules()
        self.category_cache = {}  # Cache: name -> YNAB category ID
        self.category_id_to_name = {}  # Cache: ID -> name
        self._initialize_category_cache()

        # Initialize LLM client if API key is available
        self.anthropic_client = None
        if ANTHROPIC_AVAILABLE and os.getenv('ANTHROPIC_API_KEY'):
            try:
                self.anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            except Exception as e:
                print(f"⚠ Could not initialize Anthropic client: {e}")

    def _load_rules(self) -> Dict:
        """Load category rules from YAML file"""
        try:
            if not os.path.exists(self.config_path):
                print(f"⚠ Category rules file not found: {self.config_path}")
                return {'rules': [], 'conservative': {'minimum_confidence': 0.75}}

            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config if config else {'rules': [], 'conservative': {'minimum_confidence': 0.75}}
        except Exception as e:
            print(f"⚠ Error loading category rules: {e}")
            return {'rules': [], 'conservative': {'minimum_confidence': 0.75}}

    def _initialize_category_cache(self):
        """Fetch YNAB categories and build name->ID and ID->name caches"""
        try:
            category_groups = self.ynab_client.get_categories()
            for group in category_groups:
                if hasattr(group, 'categories') and group.categories:
                    for cat in group.categories:
                        if not cat.hidden and not cat.deleted:
                            # Store both ways for lookups
                            self.category_cache[cat.name] = cat.id
                            self.category_id_to_name[cat.id] = cat.name
        except Exception as e:
            print(f"⚠ Error fetching YNAB categories: {e}")

    def _clean_text(self, text: str) -> str:
        """
        Clean text before classification by removing URLs and extra whitespace

        Args:
            text: Raw text from transaction (payee, memo, item name, etc.)

        Returns:
            Cleaned text suitable for keyword matching
        """
        if not text:
            return ""

        # Remove Amazon order links (common in memos)
        text = re.sub(r'Amazon Link:\s*https?://[^\s]+', '', text, flags=re.IGNORECASE)

        # Remove other URLs
        text = re.sub(r'https?://[^\s]+', '', text)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def classify_amazon_transaction(self, amazon_txn: Dict, ynab_txn) -> Optional[str]:
        """
        Classify Amazon transaction using item name

        Args:
            amazon_txn: Parsed Amazon transaction with 'items' and 'item_name_from_subject'
            ynab_txn: Matched YNAB transaction object

        Returns:
            YNAB category_id or None
        """
        # Extract most prominent item name
        # Priority: item_name_from_subject > first item > None
        item_name = None
        if amazon_txn.get('item_name_from_subject'):
            item_name = amazon_txn['item_name_from_subject']
        elif amazon_txn.get('items') and len(amazon_txn['items']) > 0:
            item_name = amazon_txn['items'][0].get('name')

        if not item_name:
            return None

        # Clean text before matching (remove URLs, extra whitespace)
        item_name = self._clean_text(item_name)

        # Check if LLM should be used first for this source
        force_llm_sources = self.rules.get('llm', {}).get('force_llm_for', [])
        use_llm_first = 'amazon' in [s.lower() for s in force_llm_sources]

        category_name = None
        confidence = 0.0

        if use_llm_first:
            # LLM-first: Skip keyword rules for Amazon transactions
            category_name, confidence = self._classify_with_llm(item_name)
        else:
            # Standard flow: Try rule-based matching first
            category_name, confidence = self._match_rules(item_name)

        # Check confidence threshold
        min_confidence = self.rules.get('conservative', {}).get('minimum_confidence', 0.75)
        if confidence < min_confidence:
            # If rules failed (or weren't tried), try LLM fallback
            if not use_llm_first:
                category_name, confidence = self._classify_with_llm(item_name)
                if confidence < min_confidence:
                    return None
            else:
                return None

        # Map category name to YNAB ID
        if category_name:
            category_id = self._map_category_to_id(category_name)
            return category_id

        return None

    def classify_venmo_transaction(self, venmo_txn: Dict) -> Optional[str]:
        """
        Classify Venmo transaction using payee/note

        Args:
            venmo_txn: Parsed Venmo transaction with 'name' and 'description'

        Returns:
            YNAB category_id or None
        """
        # Combine payee name and description for matching
        text_parts = []
        if venmo_txn.get('name'):
            text_parts.append(venmo_txn['name'])
        if venmo_txn.get('description'):
            text_parts.append(venmo_txn['description'])

        if not text_parts:
            return None

        text = ' '.join(text_parts)

        # Clean text before matching (remove URLs, extra whitespace)
        text = self._clean_text(text)

        # Check if LLM should be used first for this source
        force_llm_sources = self.rules.get('llm', {}).get('force_llm_for', [])
        use_llm_first = 'venmo' in [s.lower() for s in force_llm_sources]

        category_name = None
        confidence = 0.0

        if use_llm_first:
            # LLM-first: Skip keyword rules for Venmo transactions
            category_name, confidence = self._classify_with_llm(text)
        else:
            # Standard flow: Try rule-based matching first
            category_name, confidence = self._match_rules(text)

        # Check confidence threshold
        min_confidence = self.rules.get('conservative', {}).get('minimum_confidence', 0.75)
        if confidence < min_confidence:
            # If rules failed (or weren't tried), try LLM fallback
            if not use_llm_first:
                category_name, confidence = self._classify_with_llm(text)
                if confidence < min_confidence:
                    return None
            else:
                return None

        # Map category name to YNAB ID
        if category_name:
            category_id = self._map_category_to_id(category_name)
            return category_id

        return None

    def classify_generic_transaction(self, text: str) -> Optional[str]:
        """
        Classify any transaction using generic text (for bulk categorization)

        Args:
            text: Payee name, memo, or any transaction text

        Returns:
            YNAB category_id or None
        """
        if not text or not text.strip():
            return None

        # Clean text before matching (remove URLs, extra whitespace)
        text = self._clean_text(text)

        # Try rule-based matching
        category_name, confidence = self._match_rules(text)

        # Check confidence threshold
        min_confidence = self.rules.get('conservative', {}).get('minimum_confidence', 0.75)
        if confidence < min_confidence:
            # LLM fallback: use Claude Haiku to classify
            category_name, confidence = self._classify_with_llm(text)
            if confidence < min_confidence:
                return None

        # Map category name to YNAB ID
        if category_name:
            category_id = self._map_category_to_id(category_name)
            return category_id

        return None

    def _match_rules(self, text: str) -> Tuple[Optional[str], float]:
        """
        Match text against keyword rules (generic, not platform-specific)

        Args:
            text: Item name, payee, or memo text to classify

        Returns:
            (category_name, confidence) or (None, 0.0)
        """
        if not text:
            return (None, 0.0)

        text_lower = text.lower()
        rules = self.rules.get('rules', [])

        if not rules:
            return (None, 0.0)

        # Context-aware exclusions: skip certain categories based on context
        # If payee contains "restaurant", "cafe", "bar", don't match pet keywords
        is_food_establishment = any(word in text_lower for word in ['restaurant', 'cafe', 'bar', 'grill', 'kitchen', 'bistro'])

        # Find best matching rule
        best_match = None
        best_confidence = 0.0

        for rule in rules:
            category = rule.get('category')
            keywords = rule.get('keywords', [])
            rule_confidence = rule.get('confidence', 0.9)

            # Skip pet category for food establishments (e.g., "Lazy Dog Restaurant")
            if is_food_establishment and category == "Mochi":
                continue

            # Check if any keyword matches (use word boundaries to avoid substring matches)
            for keyword in keywords:
                keyword_lower = keyword.lower()
                # Use regex word boundaries to match complete words only
                # This prevents "mobil" from matching "Mobile" and "pet" from matching "Petite"
                pattern = r'\b' + re.escape(keyword_lower) + r'\b'
                if re.search(pattern, text_lower):
                    # Found a match
                    if rule_confidence > best_confidence:
                        best_match = category
                        best_confidence = rule_confidence
                    break  # Move to next rule once we found a match

        return (best_match, best_confidence)

    def _classify_with_llm(self, text: str) -> Tuple[Optional[str], float]:
        """
        Use Claude Haiku LLM to classify transaction text when rules don't match

        Args:
            text: Transaction text (item name, payee, memo, etc.)

        Returns:
            (category_name, confidence) or (None, 0.0)
        """
        if not self.anthropic_client:
            return (None, 0.0)

        try:
            # Get available categories for the prompt
            category_list = [name for name in self.category_cache.keys()]
            if not category_list:
                return (None, 0.0)

            # Build structured prompt
            prompt = f"""You are a financial transaction categorizer. Given a transaction description, classify it into one of the available budget categories.

Transaction description: "{text}"

Available categories:
{chr(10).join(f'- {cat}' for cat in sorted(category_list))}

Analyze the transaction description and determine the most appropriate category. Consider:
- Product type (baby items, groceries, electronics, pet supplies, etc.)
- Merchant type (restaurant, pharmacy, retailer, etc.)
- Context clues in the description

Respond ONLY with a JSON object in this exact format:
{{
  "category": "category name from the list above",
  "confidence": 0.XX (between 0.0 and 1.0, where 1.0 is completely certain),
  "reasoning": "brief explanation"
}}

If you cannot confidently categorize (confidence < 0.8), respond with:
{{
  "category": null,
  "confidence": 0.0,
  "reasoning": "explanation of why it's unclear"
}}"""

            # Call Claude Haiku
            message = self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = message.content[0].text.strip()

            # Extract JSON from response (handle markdown code blocks)
            import json
            if '```json' in response_text:
                json_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                json_text = response_text.split('```')[1].split('```')[0].strip()
            else:
                json_text = response_text

            result = json.loads(json_text)

            category = result.get('category')
            confidence = float(result.get('confidence', 0.0))

            # Apply LLM confidence threshold
            llm_threshold = self.rules.get('llm', {}).get('confidence_threshold', 0.8)
            if confidence < llm_threshold:
                return (None, 0.0)

            return (category, confidence)

        except Exception as e:
            print(f"    ⚠ LLM classification error: {e}")
            return (None, 0.0)

    def _map_category_to_id(self, category_name: str) -> Optional[str]:
        """
        Map category name to YNAB ID with exact and fuzzy matching

        Args:
            category_name: Category name from rules

        Returns:
            YNAB category ID or None
        """
        if not category_name:
            return None

        # Try exact match first
        if category_name in self.category_cache:
            return self.category_cache[category_name]

        # Try fuzzy matching (remove emojis and compare)
        best_match = None
        best_ratio = 0.0

        for ynab_name, ynab_id in self.category_cache.items():
            # Remove emojis and compare
            ynab_clean = ''.join(char for char in ynab_name if char.isalnum() or char.isspace())
            rule_clean = ''.join(char for char in category_name if char.isalnum() or char.isspace())

            # Calculate similarity
            ratio = SequenceMatcher(None, rule_clean.lower().strip(), ynab_clean.lower().strip()).ratio()

            if ratio > best_ratio and ratio > 0.8:  # 80% similarity threshold
                best_match = ynab_id
                best_ratio = ratio

        if best_match:
            return best_match

        # No match found
        print(f"⚠ Could not find YNAB category for: '{category_name}'")
        return None

    def get_category_name(self, category_id: str) -> Optional[str]:
        """
        Get category name from ID

        Args:
            category_id: YNAB category ID

        Returns:
            Category name or None
        """
        return self.category_id_to_name.get(category_id)
