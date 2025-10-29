#!/usr/bin/env python3
"""
Compound Matching Strategies

Implements the Strategy Pattern for different compound matching approaches.
Each strategy provides a different method for matching compound names
to knowledge graph entities.

Strategies:
1. ExactMatcher - Direct string matching (name, synonyms)
2. NormalizedMatcher - Matching with name normalization
3. FuzzyMatcher - Fuzzy string matching with configurable threshold
4. OAKMatcher - Ontology Access Kit based matching (future)
"""

import pandas as pd
from abc import ABC, abstractmethod
from typing import Optional, Dict, List, Tuple
from fuzzywuzzy import fuzz
import logging

from .compound_normalizer import CompoundNameNormalizer

logger = logging.getLogger(__name__)


class MatchingStrategy(ABC):
    """Abstract base class for matching strategies."""

    def __init__(self, kg_data: pd.DataFrame):
        """
        Initialize the matching strategy.

        Args:
            kg_data: Knowledge graph nodes DataFrame with columns:
                - id: Node identifier
                - name: Primary name
                - synonym: Pipe-separated synonyms
                - category: Node category
        """
        self.kg_data = kg_data
        self.normalizer = CompoundNameNormalizer()

    @abstractmethod
    def match(self, compound_name: str) -> Optional[str]:
        """
        Find the best matching KG node ID for a compound name.

        Args:
            compound_name: Compound name to match

        Returns:
            KG node ID if match found, None otherwise
        """
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return the name of this matching strategy."""
        pass


class ExactMatcher(MatchingStrategy):
    """Exact string matching strategy (case-insensitive)."""

    def __init__(self, kg_data: pd.DataFrame):
        super().__init__(kg_data)
        self._build_lookup_dict()

    def _build_lookup_dict(self):
        """Build lookup dictionary for O(1) exact matching."""
        self.name_to_id = {}
        self.synonym_to_id = {}

        for _, row in self.kg_data.iterrows():
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')

            # Add primary name
            if pd.notna(name) and name.strip():
                key = name.lower().strip()
                self.name_to_id[key] = node_id

            # Add synonyms
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    key = synonym.lower().strip()
                    self.synonym_to_id[key] = node_id

        logger.info(f"ExactMatcher: Built lookup with {len(self.name_to_id)} names, "
                   f"{len(self.synonym_to_id)} synonyms")

    def match(self, compound_name: str) -> Optional[str]:
        """Match using exact string comparison."""
        if not compound_name or not isinstance(compound_name, str):
            return None

        # Skip water
        if compound_name.lower().strip() in ['distilled water', 'water']:
            return None

        key = compound_name.lower().strip()

        # Try name lookup
        if key in self.name_to_id:
            return self.name_to_id[key]

        # Try synonym lookup
        if key in self.synonym_to_id:
            return self.synonym_to_id[key]

        return None

    def get_strategy_name(self) -> str:
        return "exact"


class NormalizedMatcher(MatchingStrategy):
    """Matching with compound name normalization."""

    def __init__(self, kg_data: pd.DataFrame):
        super().__init__(kg_data)
        self._build_lookup_dict()

    def _build_lookup_dict(self):
        """Build lookup dictionary with normalized names."""
        self.normalized_to_id = {}

        for _, row in self.kg_data.iterrows():
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')

            # Normalize and add primary name
            if pd.notna(name) and name.strip():
                norm_name = self.normalizer.normalize(name)
                if norm_name:
                    self.normalized_to_id[norm_name] = node_id

            # Normalize and add synonyms
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    norm_syn = self.normalizer.normalize(synonym)
                    if norm_syn:
                        self.normalized_to_id[norm_syn] = node_id

        logger.info(f"NormalizedMatcher: Built lookup with {len(self.normalized_to_id)} normalized names")

    def match(self, compound_name: str) -> Optional[str]:
        """Match using normalized compound names."""
        if not compound_name or not isinstance(compound_name, str):
            return None

        # Skip water
        if compound_name.lower().strip() in ['distilled water', 'water']:
            return None

        # Normalize the input
        normalized = self.normalizer.normalize(compound_name)
        if not normalized:
            return None

        # Lookup normalized name
        return self.normalized_to_id.get(normalized)

    def get_strategy_name(self) -> str:
        return "normalized"


class FuzzyMatcher(MatchingStrategy):
    """Fuzzy string matching strategy using fuzzywuzzy."""

    def __init__(self, kg_data: pd.DataFrame, similarity_threshold: int = 85):
        """
        Initialize fuzzy matcher.

        Args:
            kg_data: Knowledge graph nodes DataFrame
            similarity_threshold: Minimum similarity score (0-100)
        """
        super().__init__(kg_data)
        self.similarity_threshold = similarity_threshold
        self._build_search_space()

    def _build_search_space(self):
        """Build search space with all names, synonyms, and normalized versions."""
        self.all_names = {}  # Maps name → node_id

        for _, row in self.kg_data.iterrows():
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')

            # Add primary name (lowercase)
            if pd.notna(name) and name.strip():
                self.all_names[name.lower().strip()] = node_id

            # Add normalized version
            if pd.notna(name) and name.strip():
                norm_name = self.normalizer.normalize(name)
                if norm_name:
                    self.all_names[norm_name] = node_id

            # Add synonyms (lowercase)
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    self.all_names[synonym.lower().strip()] = node_id
                    # Add normalized synonym
                    norm_syn = self.normalizer.normalize(synonym)
                    if norm_syn:
                        self.all_names[norm_syn] = node_id

        logger.info(f"FuzzyMatcher: Built search space with {len(self.all_names)} entries, "
                   f"threshold={self.similarity_threshold}")

    def match(self, compound_name: str) -> Optional[str]:
        """Match using fuzzy string similarity."""
        if not compound_name or not isinstance(compound_name, str):
            return None

        # Skip water
        if compound_name.lower().strip() in ['distilled water', 'water']:
            return None

        original_name = compound_name.lower().strip()
        normalized_name = self.normalizer.normalize(compound_name)

        best_match_id = None
        best_score = 0

        # Search through all names
        for kg_name, kg_id in self.all_names.items():
            # Try matching against original name
            score1 = fuzz.ratio(original_name, kg_name)
            # Try matching against normalized name
            score2 = fuzz.ratio(normalized_name, kg_name) if normalized_name else 0

            max_score = max(score1, score2)

            if max_score > best_score and max_score >= self.similarity_threshold:
                best_score = max_score
                best_match_id = kg_id

        if best_match_id and best_score >= 90:  # Only log high-confidence fuzzy matches
            logger.debug(f"Fuzzy matched '{compound_name}' with score {best_score}")

        return best_match_id

    def get_strategy_name(self) -> str:
        return f"fuzzy({self.similarity_threshold})"


class ChainedMatcher(MatchingStrategy):
    """
    Chains multiple matching strategies in order of precision.

    Tries strategies in sequence:
    1. Exact matching (fastest, most precise)
    2. Normalized matching (medium speed, good precision)
    3. Fuzzy matching (slowest, least precise)

    Returns first successful match.
    """

    def __init__(self, kg_data: pd.DataFrame,
                 fuzzy_threshold: int = 85,
                 enable_fuzzy: bool = True):
        """
        Initialize chained matcher.

        Args:
            kg_data: Knowledge graph nodes DataFrame
            fuzzy_threshold: Threshold for fuzzy matching
            enable_fuzzy: Whether to include fuzzy matching
        """
        super().__init__(kg_data)

        # Initialize all strategies
        self.strategies: List[Tuple[MatchingStrategy, str]] = []

        # Add exact matcher
        exact_matcher = ExactMatcher(kg_data)
        self.strategies.append((exact_matcher, "exact"))

        # Add normalized matcher
        normalized_matcher = NormalizedMatcher(kg_data)
        self.strategies.append((normalized_matcher, "normalized"))

        # Add fuzzy matcher if enabled
        if enable_fuzzy:
            fuzzy_matcher = FuzzyMatcher(kg_data, fuzzy_threshold)
            self.strategies.append((fuzzy_matcher, "fuzzy"))

        logger.info(f"ChainedMatcher: Initialized with {len(self.strategies)} strategies")

    def match(self, compound_name: str) -> Optional[str]:
        """
        Try each strategy in sequence until a match is found.

        Args:
            compound_name: Compound name to match

        Returns:
            Tuple of (node_id, strategy_name) if match found, (None, None) otherwise
        """
        for strategy, strategy_name in self.strategies:
            result = strategy.match(compound_name)
            if result:
                return result

        return None

    def match_with_method(self, compound_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Match and return which strategy succeeded.

        Args:
            compound_name: Compound name to match

        Returns:
            Tuple of (node_id, strategy_name) if match found, (None, None) otherwise
        """
        for strategy, strategy_name in self.strategies:
            result = strategy.match(compound_name)
            if result:
                return (result, strategy_name)

        return (None, None)

    def get_strategy_name(self) -> str:
        strategy_names = [s[1] for s in self.strategies]
        return f"chained({','.join(strategy_names)})"
