import json
import logging
import os
from typing import Any, Dict, List

_logger = logging.getLogger(__name__)

_HEURISTICS_CACHE: Dict[str, Any] | None = None

_DEFAULTS: Dict[str, Any] = {
    "category_synonyms": {
        "smartphones": [
            "phone",
            "phones",
            "mobile",
            "mobiles",
            "cell",
            "cellphone",
            "cellphones",
            "handset",
        ],
        "laptops": ["laptop", "laptops", "notebook", "notebooks", "ultrabook"],
        "televisions": ["tv", "tvs", "television", "oled tv", "led tv"],
        "smartwatches": ["watch", "watches", "smartwatch", "smartwatches"],
        "tablets": ["tablet", "tablets"],
        "cameras": ["camera", "cameras"],
    },
    "brand_synonyms": {},
    "intent_keywords": {
        "cart": ["cart", "add", "remove", "buy", "purchase", "order", "checkout"],
        "support": ["policy", "return", "shipping", "warranty", "support", "contact", "refund"],
        "recommendation": ["recommend", "suggest", "trending", "popular", "gift"],
        "search": ["show", "find", "search", "browse", "get", "want", "need"],
        "compare": ["compare", "vs", "versus", "difference between", "which is better"],
    },
    "generic_nouns": [
        "phone",
        "phones",
        "laptop",
        "laptops",
        "watch",
        "watches",
        "tv",
        "tvs",
        "camera",
        "cameras",
    ],
    "phrases": {
        "in_stock": ["in stock", "available now", "instock", "ready to ship"],
        "out_of_stock": ["sold out", "out of stock", "unavailable"],
        # Triggers indicating the user is asking about items from prior results or follow-ups
        "follow_up": [
            "first option",
            "second option",
            "third option",
            "tell me about",
            "more about",
        ],
        # Lightweight indicators used to flag a follow-up tone in the analysis block
        "followup_indicators": [
            "more",
            "other",
            "different",
            "cheaper",
            "better",
            "similar",
        ],
    },
    "rating_patterns": [
        r"(\d(?:\.\d)?)\s*\+\s*stars",
        r"at\s+least\s+(\d(?:\.\d)?)\s*stars",
        r"rating\s*(?:of\s*)?(?:over|above|>=?|at\s+least)\s*(\d(?:\.\d)?)",
        r"(\d(?:\.\d)?)\s*stars\s*(?:or\s*more|and\s*up)",
    ],
    "discount_patterns": [
        r"(\d{1,3})\s*%\s*(?:off|discount)",
        r"at\s+least\s+(\d{1,3})\s*%",
    ],
    "thresholds": {
        "fuzzy_similarity_brand": 90,
        "fuzzy_similarity_category": 90,
        "fuzzy_unambiguous_margin": 3,
        "min_token_length": 3,
    },
    "feature_flags": {
        "fallback_fuzzy_brand": False,
        "fallback_fuzzy_category": False,
    },
    # Generic refine terms used to decide when to keep the previous query as the base
    # rather than replacing it with purely generic tokens (e.g., "cheaper", "under").
    "refine_generic_terms": [
        "cheaper",
        "under",
        "over",
        "below",
        "above",
        "minimum",
        "max",
        "at",
        "least",
        "most",
        "only",
        "in",
        "stock",
        "higher",
        "rating",
        "better",
        "rated",
        "less",
        "expensive",
        "lower",
        "price",
        "up",
        "to",
    ],
}


def get_heuristics() -> Dict[str, Any]:
    """Load heuristics config from repo-local file with safe defaults and caching.

    Source of truth:
    - Local file at fallback_config/heuristics.json (repo-local)

    Any missing keys fall back to in-code defaults. Result is cached in-process.
    """
    global _HEURISTICS_CACHE
    if _HEURISTICS_CACHE is not None:
        return _HEURISTICS_CACHE

    data: Dict[str, Any] = {}

    # Load repo-local config file only
    repo_root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(repo_root, "fallback_config", "heuristics.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _logger.info("Loaded heuristics from local file: %s", path)
    except FileNotFoundError:
        _logger.info("Heuristics config not found at %s; using defaults", path)
        data = {}
    except Exception as e:
        _logger.warning("Heuristics config load error (%s); using defaults", e)
        data = {}

    # Merge with defaults: shallow for most keys, but deep-merge for intent_keywords
    merged = {**_DEFAULTS, **(data or {})}
    try:
        dk = (data or {}).get("intent_keywords", {}) or {}
        if isinstance(dk, dict):
            merged_intents = {**_DEFAULTS.get("intent_keywords", {}), **dk}
            merged["intent_keywords"] = merged_intents
    except Exception:
        pass
    _HEURISTICS_CACHE = merged
    return merged


def build_category_synonyms_for_allowed(allowed_categories_list: List[Any]) -> Dict[str, Any]:
    """Build a synonym->canonical map limited to categories present in allowed_categories_list.
    Synonyms and canonical keys are matched case-insensitively.
    Returns mapping from synonym (lowercased) to the canonical category object.
    """
    heur = get_heuristics()
    raw_map: Dict[str, List[str]] = heur.get("category_synonyms", {}) or {}

    # Build map from lower-cased canonical name to original object (from allowed list)
    cats_lower_to_obj: Dict[str, Any] = {}
    for c in allowed_categories_list:
        try:
            key = str(c).strip().lower()
            if key:
                cats_lower_to_obj[key] = c
        except Exception:
            continue

    synonym_to_obj: Dict[str, Any] = {}
    for canonical_name, synonyms in raw_map.items():
        try:
            canon_key = str(canonical_name).strip().lower()
            canon_obj = cats_lower_to_obj.get(canon_key)
            if not canon_obj:
                # Skip synonyms that point to a category not present in allowed set
                continue
            for syn in (synonyms or []):
                try:
                    syn_key = str(syn).strip().lower()
                    if syn_key:
                        synonym_to_obj[syn_key] = canon_obj
                except Exception:
                    continue
        except Exception:
            continue

    return synonym_to_obj
