#!/usr/bin/env python3
"""
Compound Name Normalization Utilities

This module provides utilities for normalizing chemical compound names
to improve matching accuracy across different naming conventions.

Consolidates normalization logic previously duplicated across multiple
mapping scripts.
"""

import re
import pandas as pd
from typing import Optional, Tuple


class CompoundNameNormalizer:
    """
    Normalizes chemical compound names for better matching.

    Handles:
    - Stereochemistry prefixes (D-/L-/DL-/+/-)
    - Hydration notation (x N H2O, ·N H2O, .N H2O, N-hydrate, monohydrate, etc.)
    - Concentration prefixes (%, M, mg, g)
    - Parenthetical information
    - Whitespace and punctuation
    - Prefix symbols (--compound → compound)
    - Atom-name salt notation (Na-benzoate → sodium benzoate)
    - Iron oxidation notation (FeIII → Fe(III))
    - Elemental prefix (Elemental sulphur → sulphur)
    - Hydrated salts (L-Cysteine HCl x H2O → L-Cysteine)
    """

    # Hydration patterns with their regex patterns
    HYDRATION_PATTERNS = [
        (r'\s*[x×]\s*(\d+)\s*H2O', r'·\1H2O'),  # x N H2O → ·NH2O
        (r'\s*[•·]\s*(\d+)\s*H2O', r'·\1H2O'),  # • N H2O → ·NH2O
        (r'\s*\.\s*(\d+)\s*H2O', r'·\1H2O'),    # . N H2O → ·NH2O
        (r'\s+(\d+)-hydrate', r'·\1H2O'),       # N-hydrate → ·NH2O
        (r'\s*[x×]\s*H2O', r'·1H2O'),           # x H2O (no number) → ·1H2O
    ]

    # Named hydrate suffixes to water molecule count
    NAMED_HYDRATES = {
        'monohydrate': 1,
        'dihydrate': 2,
        'trihydrate': 3,
        'tetrahydrate': 4,
        'pentahydrate': 5,
        'hexahydrate': 6,
        'heptahydrate': 7,
        'octahydrate': 8,
        'nonahydrate': 9,
        'decahydrate': 10,
        'hydrate': 1,  # Generic hydrate = 1
    }

    # Atom symbol to name mappings for salt notation
    ATOM_TO_NAME = {
        'Na': 'sodium',
        'Na2': 'disodium',
        'K': 'potassium',
        'K2': 'dipotassium',
        'Ca': 'calcium',
        'Mg': 'magnesium',
        'Fe': 'iron',
        'Cu': 'copper',
        'Zn': 'zinc',
        'Al': 'aluminum',
        'NH4': 'ammonium',
    }

    # Common salt suffixes that indicate a hydrated salt form
    SALT_SUFFIXES = [
        r'\s+HCl\s*(?:[x×·]\s*\d*\s*H2O)?$',    # HCl, HCl x H2O
        r'\s+H2SO4\s*(?:[x×·]\s*\d*\s*H2O)?$',  # H2SO4
        r'\s+HBr\s*(?:[x×·]\s*\d*\s*H2O)?$',    # HBr
        r'\s+HNO3\s*(?:[x×·]\s*\d*\s*H2O)?$',   # HNO3
    ]

    # Formula notation fixes - add missing parentheses around polyatomic ions
    # Pattern: ion followed by subscript number that needs parentheses
    FORMULA_FIXES = [
        (r'NH4(\d)', r'(NH4)\1'),          # NH42 → (NH4)2
        (r'NO3(\d)', r'(NO3)\1'),          # NO32 → (NO3)2
        (r'SO4(\d)', r'(SO4)\1'),          # SO43 → (SO4)3
        (r'PO4(\d)', r'(PO4)\1'),          # PO42 → (PO4)2
        (r'MoO4(\d)', r'(MoO4)\1'),        # MoO42 → (MoO4)2
        (r'Mo7O24(\d*)', r'(Mo7O24)\1'),   # Mo7O24 → (Mo7O24) for NH46Mo7O24
        (r'OH(\d)', r'(OH)\1'),            # OH2 → (OH)2
        (r'CO3(\d)', r'(CO3)\1'),          # CO32 → (CO3)2
        (r'ClO4(\d)', r'(ClO4)\1'),        # ClO42 → (ClO4)2
        (r'SeO3(\d)', r'(SeO3)\1'),        # SeO32 → (SeO3)2
        (r'VO4(\d)', r'(VO4)\1'),          # VO42 → (VO4)2
        (r'WO4(\d)', r'(WO4)\1'),          # WO42 → (WO4)2
        (r'CrO4(\d)', r'(CrO4)\1'),        # CrO42 → (CrO4)2
    ]

    # Greek letter mappings
    GREEK_TO_LATIN = {
        'α': 'alpha',
        'β': 'beta',
        'ß': 'beta',  # German eszett often used for beta
        'γ': 'gamma',
        'δ': 'delta',
        'ε': 'epsilon',
        'λ': 'lambda',
        'ω': 'omega',
    }

    # Stereochemistry prefix fixes
    STEREO_FIXES = [
        (r'^D\+-', 'D-'),       # D+-Glucose → D-Glucose
        (r'^L\+-', 'L-'),       # L+-Tartaric → L-Tartaric
        (r'^D-\+-', 'D-'),      # D-+-biotin → D-biotin
        (r'^L-\+-', 'L-'),      # L-+-something → L-something
        (r'^DL\+-', 'DL-'),     # DL+-amino acid → DL-amino acid
        (r'^\(\+\)-', ''),      # (+)-compound → compound
        (r'^\(-\)-', ''),       # (-)-compound → compound
        (r'^\(±\)-', 'DL-'),    # (±)-compound → DL-compound
    ]

    # Chemical formula to common name mappings for PubChem lookup
    # PubChem works better with names than formulas
    FORMULA_TO_NAME = {
        # Iron compounds
        'Fe2(SO4)3': 'iron(III) sulfate',
        'FeSO4': 'iron(II) sulfate',
        'FeCl2': 'iron(II) chloride',
        'FeCl3': 'iron(III) chloride',
        'Fe(NO3)3': 'iron(III) nitrate',
        'Fe(NH4)2(SO4)2': 'ammonium iron(II) sulfate',
        'FeNH4(SO4)2': 'ammonium iron(III) sulfate',
        # Ammonium compounds
        '(NH4)2SO4': 'ammonium sulfate',
        '(NH4)2CO3': 'ammonium carbonate',
        '(NH4)2HPO4': 'diammonium hydrogen phosphate',
        'NH4Cl': 'ammonium chloride',
        'NH4NO3': 'ammonium nitrate',
        '(NH4)6Mo7O24': 'ammonium molybdate',
        # Calcium compounds
        'Ca(NO3)2': 'calcium nitrate',
        'CaCl2': 'calcium chloride',
        'CaSO4': 'calcium sulfate',
        'Ca(OH)2': 'calcium hydroxide',
        # Magnesium compounds
        'MgSO4': 'magnesium sulfate',
        'MgCl2': 'magnesium chloride',
        'Mg(NO3)2': 'magnesium nitrate',
        # Sodium compounds
        'Na2SO4': 'sodium sulfate',
        'Na2CO3': 'sodium carbonate',
        'NaHCO3': 'sodium bicarbonate',
        'Na2HPO4': 'disodium hydrogen phosphate',
        'NaH2PO4': 'sodium dihydrogen phosphate',
        'Na2MoO4': 'sodium molybdate',
        'Na2SeO3': 'sodium selenite',
        'Na2WO4': 'sodium tungstate',
        # Potassium compounds
        'K2SO4': 'potassium sulfate',
        'K2CO3': 'potassium carbonate',
        'KH2PO4': 'potassium dihydrogen phosphate',
        'K2HPO4': 'dipotassium hydrogen phosphate',
        'KNO3': 'potassium nitrate',
        # Zinc compounds
        'ZnSO4': 'zinc sulfate',
        'ZnCl2': 'zinc chloride',
        'Zn(NO3)2': 'zinc nitrate',
        # Copper compounds
        'CuSO4': 'copper(II) sulfate',
        'CuCl2': 'copper(II) chloride',
        'Cu(NO3)2': 'copper(II) nitrate',
        # Manganese compounds
        'MnSO4': 'manganese(II) sulfate',
        'MnCl2': 'manganese(II) chloride',
        'Mn(NO3)2': 'manganese(II) nitrate',
        # Cobalt compounds
        'CoCl2': 'cobalt(II) chloride',
        'CoSO4': 'cobalt(II) sulfate',
        'Co(NO3)2': 'cobalt(II) nitrate',
        # Nickel compounds
        'NiCl2': 'nickel(II) chloride',
        'NiSO4': 'nickel(II) sulfate',
        'Ni(NO3)2': 'nickel(II) nitrate',
        # Aluminum compounds
        'Al2(SO4)3': 'aluminum sulfate',
        'AlCl3': 'aluminum chloride',
        'Al(NO3)3': 'aluminum nitrate',
        'AlK(SO4)2': 'potassium aluminum sulfate',
        # Barium compounds
        'BaCl2': 'barium chloride',
        'Ba(NO3)2': 'barium nitrate',
        # Chromium compounds
        'CrCl3': 'chromium(III) chloride',
        'Cr(NO3)3': 'chromium(III) nitrate',
        'CrK(SO4)2': 'potassium chromium(III) sulfate',
        # Rare earth compounds
        'Ce(NO3)3': 'cerium(III) nitrate',
        'La(NO3)3': 'lanthanum(III) nitrate',
        # Other compounds
        'H3BO3': 'boric acid',
        'Na2B4O7': 'sodium tetraborate',
        'KIO3': 'potassium iodate',
        'NaF': 'sodium fluoride',
        'KBr': 'potassium bromide',
        'NaBr': 'sodium bromide',
    }

    # Buffer compounds - map buffer names to their chemical compound names
    BUFFER_COMPOUNDS = {
        'HEPES': '4-(2-hydroxyethyl)-1-piperazineethanesulfonic acid',
        'MES': '2-(N-morpholino)ethanesulfonic acid',
        'PIPES': "piperazine-N,N'-bis(2-ethanesulfonic acid)",
        'MOPS': '3-(N-morpholino)propanesulfonic acid',
        'Tris': 'tris(hydroxymethyl)aminomethane',
        'TRIS': 'tris(hydroxymethyl)aminomethane',
        'TES': "N-[tris(hydroxymethyl)methyl]-2-aminoethanesulfonic acid",
        'CAPS': '3-(cyclohexylamino)-1-propanesulfonic acid',
        'CHES': '2-(cyclohexylamino)ethanesulfonic acid',
        'EPPS': '4-(2-hydroxyethyl)-1-piperazinepropanesulfonic acid',
        'HEPPSO': '4-(2-hydroxyethyl)piperazine-1-(2-hydroxypropanesulfonic acid)',
        'Bicine': 'N,N-bis(2-hydroxyethyl)glycine',
        'Tricine': 'N-[tris(hydroxymethyl)methyl]glycine',
        'ADA': 'N-(2-acetamido)iminodiacetic acid',
        'BIS-TRIS': 'bis(2-hydroxyethyl)amino-tris(hydroxymethyl)methane',
    }

    def __init__(self):
        """Initialize the normalizer."""
        pass

    def normalize(self, name: str,
                  remove_hydration: bool = True,
                  remove_stereochemistry: bool = True,
                  remove_concentrations: bool = True,
                  remove_parenthetical: bool = True) -> str:
        """
        Normalize a chemical compound name.

        Args:
            name: Chemical compound name to normalize
            remove_hydration: Remove hydration notation (default: True)
            remove_stereochemistry: Remove D-/L-/DL- prefixes (default: True)
            remove_concentrations: Remove concentration prefixes (default: True)
            remove_parenthetical: Remove parenthetical info (default: True)

        Returns:
            Normalized compound name (lowercase, trimmed)
        """
        if pd.isna(name) or name == "" or not isinstance(name, str):
            return ""

        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove concentration/quantity prefixes if requested
        if remove_concentrations:
            # Matches: percentages (0.2%), molarities (1 M), weights (100 mg, 1 g), or "G " prefix
            normalized = re.sub(
                r'^(?:\d+\.?\d*\s*%\s+|\d+\.?\d*\s+[mM]\s+|\d+\.?\d*\s*[Mm]?[Gg]\s+|[Gg]\s+)',
                '',
                normalized
            )

        # Remove stereochemistry prefixes if requested
        if remove_stereochemistry:
            # Combined prefix removal (D-/L-/DL- and +/-)
            normalized = re.sub(r'^(?:[dl]|dl|\+|-)-?\s*', '', normalized)

        # Remove or normalize hydration notation
        if remove_hydration:
            # Remove hydration notation entirely
            normalized = re.sub(r'\s*[x•\.×·]\s*\d+\s*h2o', '', normalized)
            normalized = re.sub(r'\s+\d+-hydrate\b', '', normalized)

        # Remove parenthetical information if requested
        if remove_parenthetical:
            normalized = re.sub(r'\([^)]*\)', '', normalized)

        # Normalize whitespace and punctuation
        normalized = re.sub(r'[,;\s]+', ' ', normalized).strip()

        return normalized

    def standardize_hydrate_notation(self, name: str) -> str:
        """
        Standardize hydration notation to ·NH2O format.

        Converts various formats:
        - "CoCl2 x 6 H2O" → "CoCl2·6H2O"
        - "MgSO4 6-hydrate" → "MgSO4·6H2O"
        - "Na2SO4.10H2O" → "Na2SO4·10H2O"

        Args:
            name: Chemical compound name

        Returns:
            Compound name with standardized hydration notation
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # Apply each hydration pattern
        for pattern, replacement in self.HYDRATION_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def extract_hydrate_info(self, name: str) -> Tuple[str, Optional[int]]:
        """
        Extract base compound and hydration number.

        Args:
            name: Chemical compound name

        Returns:
            Tuple of (base_compound, water_molecules)
            water_molecules is None if no hydration found

        Examples:
            >>> normalizer.extract_hydrate_info("CoCl2 x 6 H2O")
            ("CoCl2", 6)
            >>> normalizer.extract_hydrate_info("MgSO4 7-hydrate")
            ("MgSO4", 7)
            >>> normalizer.extract_hydrate_info("NaCl")
            ("NaCl", None)
        """
        if not name or not isinstance(name, str):
            return (name, None)

        # Try each hydration pattern
        patterns = [
            (r'(.+?)\s*[x×]\s*(\d+)\s*H2O', 'x N H2O'),
            (r'(.+?)\s*[•·]\s*(\d+)\s*H2O', '· N H2O'),
            (r'(.+?)\s*\.\s*(\d+)\s*H2O', '. N H2O'),
            (r'(.+?)\s+(\d+)-hydrate', 'N-hydrate'),
        ]

        for pattern, _ in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                base_compound = match.group(1).strip()
                water_count = int(match.group(2))
                return (base_compound, water_count)

        # No hydration found
        return (name, None)

    def is_chemical_formula(self, name: str) -> bool:
        """
        Detect if a string looks like a chemical formula.

        Looks for patterns like:
        - NaCl
        - CaCl2
        - H2SO4
        - Fe(NO3)3
        - CoCl2 x 6 H2O

        Args:
            name: String to check

        Returns:
            True if it looks like a chemical formula
        """
        if not name or not isinstance(name, str):
            return False

        # Remove hydration notation for formula detection
        cleaned = re.sub(r'\s*[x•\.×·]\s*\d+\s*H2O', '', name, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+\d+-hydrate\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        # Pattern for chemical formulas:
        # - Starts with uppercase letter
        # - Contains element symbols (1-2 letters)
        # - May contain numbers, parentheses, brackets
        # - May contain charges (+/-/2+/2-/etc)
        formula_pattern = r'^[A-Z][a-z]?(\d+)?(\([A-Z][a-z]?(\d+)?\))?([A-Z][a-z]?(\d+)?)*(\d*[+-])?$'

        return bool(re.match(formula_pattern, cleaned))

    def clean_malformed_entry(self, name: str) -> str:
        """
        Clean malformed entries with prefixes/suffixes.

        Handles:
        - Leading numbers: "(1) CaCl2" → "CaCl2"
        - Hash marks: "# Vitamin solution" → "Vitamin solution"
        - Asterisks: "*Tryptone" → "Tryptone"
        - Plus/minus: "+ 0.02% Yeast extract" → "Yeast extract"

        Args:
            name: Potentially malformed compound name

        Returns:
            Cleaned compound name
        """
        if not name or not isinstance(name, str):
            return name

        cleaned = name.strip()

        # Remove leading special characters and numbers in parentheses
        cleaned = re.sub(r'^\([0-9]+\)\s*', '', cleaned)
        cleaned = re.sub(r'^[#\*\+\-]\s*', '', cleaned)

        # Remove trailing special characters
        cleaned = re.sub(r'\s*[\*\+\-]$', '', cleaned)

        return cleaned.strip()

    def remove_prefix_symbols(self, name: str) -> str:
        """
        Remove leading prefix symbols like --, ++, etc.

        Examples:
            "--Chloramphenicol" → "Chloramphenicol"
            "--Quinic acid" → "Quinic acid"

        Args:
            name: Compound name with potential prefix symbols

        Returns:
            Cleaned compound name
        """
        if not name or not isinstance(name, str):
            return name

        # Remove leading dashes, pluses, or other symbols
        cleaned = re.sub(r'^[\-\+\*\#]+\s*', '', name.strip())
        return cleaned

    def remove_named_hydrate_suffix(self, name: str) -> str:
        """
        Remove named hydrate suffixes (monohydrate, dihydrate, etc.).

        Examples:
            "Ferric citrate monohydrate" → "Ferric citrate"
            "Calcium chloride dihydrate" → "Calcium chloride"

        Args:
            name: Compound name with potential hydrate suffix

        Returns:
            Base compound name without hydrate suffix
        """
        if not name or not isinstance(name, str):
            return name

        result = name
        for hydrate_name in self.NAMED_HYDRATES:
            pattern = rf'\s+{hydrate_name}$'
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        return result.strip()

    def extract_base_from_hydrated_salt(self, name: str) -> str:
        """
        Extract the base compound from a hydrated salt form.

        Examples:
            "L-Cysteine HCl x H2O" → "L-Cysteine"
            "Glycine HCl" → "Glycine"

        Args:
            name: Compound name with potential salt suffix

        Returns:
            Base compound name
        """
        if not name or not isinstance(name, str):
            return name

        result = name
        for pattern in self.SALT_SUFFIXES:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        return result.strip()

    def normalize_iron_oxidation(self, name: str) -> str:
        """
        Normalize iron oxidation state notation.

        Examples:
            "FeIII citrate" → "iron(III) citrate"
            "FeIII-EDTA" → "iron(III)-EDTA"
            "FeIIIPO4 x 4 H2O" → "iron(III) phosphate"

        Args:
            name: Compound name with iron oxidation notation

        Returns:
            Normalized compound name
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # FeIII → iron(III), FeII → iron(II)
        result = re.sub(r'\bFeIII\b', 'iron(III)', result)
        result = re.sub(r'\bFeII\b', 'iron(II)', result)

        # Handle compound formulas with iron
        # FeIIIPO4 → iron(III) phosphate
        result = re.sub(r'\bFeIIIPO4\b', 'iron(III) phosphate', result, flags=re.IGNORECASE)
        result = re.sub(r'\bFeIII-?EDTA\b', 'iron(III) EDTA', result, flags=re.IGNORECASE)
        result = re.sub(r'\bFeIIINH4-?EDTA\b', 'iron(III) ammonium EDTA', result, flags=re.IGNORECASE)

        return result

    def remove_elemental_prefix(self, name: str) -> str:
        """
        Remove 'Elemental' prefix from compound names.

        Examples:
            "Elemental sulphur" → "sulphur"
            "Elemental sulfur" → "sulfur"

        Args:
            name: Compound name with potential 'Elemental' prefix

        Returns:
            Compound name without prefix
        """
        if not name or not isinstance(name, str):
            return name

        result = re.sub(r'^Elemental\s+', '', name, flags=re.IGNORECASE)
        return result.strip()

    def normalize_atom_salt_notation(self, name: str) -> str:
        """
        Convert atom symbol salt notation to proper chemical names.

        Examples:
            "Na-benzoate" → "sodium benzoate"
            "Na2-EDTA x 2 H2O" → "disodium EDTA"
            "K-acetate" → "potassium acetate"
            "Na-acetate x 3 H2O" → "sodium acetate"

        Args:
            name: Compound name with atom-salt notation

        Returns:
            Compound name with proper chemical names
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # Pattern: Na2- or Na- at the start, followed by compound name
        for atom, full_name in sorted(self.ATOM_TO_NAME.items(), key=lambda x: -len(x[0])):
            # Match atom symbol followed by - and compound name
            pattern = rf'^{atom}-(\w+)'
            match = re.match(pattern, result)
            if match:
                compound_part = match.group(1)
                # Remove hydration suffix if present for cleaner mapping
                rest_of_name = result[match.end():]
                result = f'{full_name} {compound_part}{rest_of_name}'
                break

        # Remove hydration from result for cleaner mapping
        result = re.sub(r'\s*[x×]\s*\d+\s*H2O$', '', result, flags=re.IGNORECASE)

        return result.strip()

    def fix_formula_notation(self, name: str) -> str:
        """
        Fix missing parentheses in chemical formulas.

        Examples:
            "NH42SO4" → "(NH4)2SO4"
            "CaNO32" → "Ca(NO3)2"
            "Fe2SO43" → "Fe2(SO4)3"
            "AlKSO42" → "AlK(SO4)2"

        Args:
            name: Chemical compound name or formula

        Returns:
            Formula with corrected parentheses
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # Apply each formula fix pattern
        for pattern, replacement in self.FORMULA_FIXES:
            result = re.sub(pattern, replacement, result)

        return result

    def normalize_greek_letters(self, name: str) -> str:
        """
        Convert Greek letters to their Latin equivalents.

        Examples:
            "α-D-Glucose" → "alpha-D-Glucose"
            "ß-NAD" → "beta-NAD"
            "γ-aminobutyric acid" → "gamma-aminobutyric acid"

        Args:
            name: Compound name with potential Greek letters

        Returns:
            Name with Greek letters converted to Latin
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # Replace each Greek letter with its Latin equivalent
        for greek, latin in self.GREEK_TO_LATIN.items():
            result = result.replace(greek, latin)

        return result

    def normalize_stereochemistry_prefixes(self, name: str) -> str:
        """
        Normalize stereochemistry prefixes.

        Examples:
            "D+-Glucose" → "D-Glucose"
            "L+-Tartaric acid" → "L-Tartaric acid"
            "D-+-biotin" → "D-biotin"
            "(+)-alpha-tocopherol" → "alpha-tocopherol"

        Args:
            name: Compound name with stereochemistry prefixes

        Returns:
            Name with normalized stereochemistry prefixes
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # Apply each stereochemistry fix pattern
        for pattern, replacement in self.STEREO_FIXES:
            result = re.sub(pattern, replacement, result)

        return result

    def extract_buffer_compound(self, name: str) -> Optional[str]:
        """
        Extract the active compound from a buffer name.

        Examples:
            "HEPES buffer" → "4-(2-hydroxyethyl)-1-piperazineethanesulfonic acid"
            "MES buffer" → "2-(N-morpholino)ethanesulfonic acid"
            "Tris-HCl buffer" → "tris(hydroxymethyl)aminomethane"
            "Phosphate buffer" → None (ambiguous)

        Args:
            name: Buffer name

        Returns:
            Full chemical name of the buffer compound, or None if not found
        """
        if not name or not isinstance(name, str):
            return None

        # Check if this is a buffer
        name_upper = name.upper()
        if 'BUFFER' not in name_upper:
            return None

        # Remove 'buffer' and common suffixes to extract the buffer name
        clean_name = re.sub(r'\s*buffer\s*', ' ', name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*-?\s*HCl\s*', ' ', clean_name, flags=re.IGNORECASE)
        clean_name = clean_name.strip()

        # Look for known buffer compounds
        for buffer_name, compound in self.BUFFER_COMPOUNDS.items():
            if buffer_name.lower() in clean_name.lower():
                return compound

        return None

    def normalize_formula_spaces(self, name: str) -> str:
        """
        Remove spaces within chemical formulas.

        Examples:
            "Fe SO4 x 7 H2O" → "FeSO4 x 7 H2O"
            "Na Cl" → "NaCl"
            "Mg SO4" → "MgSO4"

        Args:
            name: Chemical formula with potential internal spaces

        Returns:
            Formula with spaces removed between chemical elements
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # Pattern for element symbol followed by space and another element/formula part
        # This handles: Fe SO4, Na Cl, Mg SO4, Ca Cl2, etc.
        # Match: Element (1-2 letters, first uppercase) + space + Element/formula part
        element_space_pattern = r'\b([A-Z][a-z]?)\s+([A-Z][a-z]?\d*(?:\([^)]+\)\d*)?)'

        # Keep applying until no more changes (handles multiple spaces)
        prev_result = None
        while prev_result != result:
            prev_result = result
            result = re.sub(element_space_pattern, r'\1\2', result)

        return result

    def convert_formula_to_name(self, name: str) -> str:
        """
        Convert chemical formula to common name for PubChem lookup.

        PubChem works better with common names than formulas.

        Examples:
            "Fe2(SO4)3" → "iron(III) sulfate"
            "(NH4)2CO3" → "ammonium carbonate"
            "Ca(NO3)2" → "calcium nitrate"

        Args:
            name: Chemical formula or name

        Returns:
            Common name if found in mapping, original name otherwise
        """
        if not name or not isinstance(name, str):
            return name

        # Try direct lookup
        if name in self.FORMULA_TO_NAME:
            return self.FORMULA_TO_NAME[name]

        # Try case-insensitive lookup (normalize whitespace too)
        name_clean = name.strip()
        for formula, common_name in self.FORMULA_TO_NAME.items():
            if formula.lower() == name_clean.lower():
                return common_name

        return name

    def is_solution_or_media(self, name: str) -> bool:
        """
        Check if the name represents a solution or media formulation.

        These should be skipped as they are mixtures, not single compounds.

        Examples:
            "Trace element solution" → True
            "Vitamin solution" → True
            "Basal medium" → True
            "Glucose" → False

        Args:
            name: Ingredient name

        Returns:
            True if this is a solution/media formulation
        """
        if not name or not isinstance(name, str):
            return False

        name_lower = name.lower()

        # Keywords that indicate solutions/media
        solution_keywords = [
            'solution',
            'medium',
            'media',
            'broth',
            'agar',
            'supplement',
            'mixture',
            'trace element',
            'vitamin mix',
            'mineral mix',
            'stock solution',
        ]

        for keyword in solution_keywords:
            if keyword in name_lower:
                return True

        return False

    def normalize_for_mapping(self, name: str) -> str:
        """
        Apply all normalizations to prepare a compound name for mapping.

        This is the main entry point for comprehensive normalization.

        Normalization order:
        1. Remove prefix symbols (--compound)
        2. Clean malformed entries
        3. Fix formula notation (NH42SO4 → (NH4)2SO4)
        4. Normalize formula spaces (Fe SO4 → FeSO4)
        5. Normalize Greek letters (α→alpha, ß→beta)
        6. Normalize stereochemistry prefixes (D+→D-, L+→L-)
        7. Remove 'Elemental' prefix
        8. Normalize iron oxidation notation
        9. Convert atom-salt notation to proper names
        10. Extract base from hydrated salts
        11. Remove named hydrate suffixes
        12. Remove hydration notation (x N H2O)
        13. Clean up whitespace

        Args:
            name: Raw compound name from source data

        Returns:
            Fully normalized compound name ready for API lookups
        """
        if not name or not isinstance(name, str):
            return ""

        result = name.strip()

        # Step 1: Remove prefix symbols (--compound)
        result = self.remove_prefix_symbols(result)

        # Step 2: Clean malformed entries
        result = self.clean_malformed_entry(result)

        # Step 3: Fix formula notation (NH42SO4 → (NH4)2SO4)
        result = self.fix_formula_notation(result)

        # Step 4: Normalize formula spaces (Fe SO4 → FeSO4)
        result = self.normalize_formula_spaces(result)

        # Step 5: Normalize Greek letters (α→alpha, ß→beta)
        result = self.normalize_greek_letters(result)

        # Step 6: Normalize stereochemistry prefixes (D+→D-, L+→L-)
        result = self.normalize_stereochemistry_prefixes(result)

        # Step 7: Remove 'Elemental' prefix
        result = self.remove_elemental_prefix(result)

        # Step 8: Normalize iron oxidation notation
        result = self.normalize_iron_oxidation(result)

        # Step 9: Convert atom-salt notation to proper names
        result = self.normalize_atom_salt_notation(result)

        # Step 10: Extract base from hydrated salts (L-Cysteine HCl x H2O → L-Cysteine)
        result = self.extract_base_from_hydrated_salt(result)

        # Step 11: Remove named hydrate suffixes (monohydrate, dihydrate, etc.)
        result = self.remove_named_hydrate_suffix(result)

        # Step 12: Remove hydration notation (x N H2O, x n H2O)
        # Also handles "x n H2O" where n is a variable
        result = re.sub(r'\s*[x×·•\.]\s*[\dn]*\s*H2O$', '', result, flags=re.IGNORECASE)

        # Step 13: Clean up whitespace
        result = re.sub(r'\s+', ' ', result).strip()

        # Step 14: Convert chemical formulas to common names (for PubChem lookup)
        result = self.convert_formula_to_name(result)

        return result


# Singleton instance for convenient access
_normalizer = CompoundNameNormalizer()

# Convenience functions
def normalize_name(name: str, **kwargs) -> str:
    """Normalize a chemical compound name (convenience function)."""
    return _normalizer.normalize(name, **kwargs)

def extract_hydrate_info(name: str) -> Tuple[str, Optional[int]]:
    """Extract base compound and hydration info (convenience function)."""
    return _normalizer.extract_hydrate_info(name)

def is_chemical_formula(name: str) -> bool:
    """Check if string looks like a chemical formula (convenience function)."""
    return _normalizer.is_chemical_formula(name)

def clean_malformed(name: str) -> str:
    """Clean malformed entry (convenience function)."""
    return _normalizer.clean_malformed_entry(name)

def normalize_for_mapping(name: str) -> str:
    """Apply all normalizations for mapping (convenience function)."""
    return _normalizer.normalize_for_mapping(name)

def fix_formula_notation(name: str) -> str:
    """Fix missing parentheses in chemical formulas (convenience function)."""
    return _normalizer.fix_formula_notation(name)

def normalize_greek_letters(name: str) -> str:
    """Convert Greek letters to Latin equivalents (convenience function)."""
    return _normalizer.normalize_greek_letters(name)

def normalize_stereochemistry_prefixes(name: str) -> str:
    """Normalize stereochemistry prefixes (convenience function)."""
    return _normalizer.normalize_stereochemistry_prefixes(name)

def extract_buffer_compound(name: str) -> Optional[str]:
    """Extract active compound from buffer name (convenience function)."""
    return _normalizer.extract_buffer_compound(name)

def normalize_formula_spaces(name: str) -> str:
    """Remove spaces within chemical formulas (convenience function)."""
    return _normalizer.normalize_formula_spaces(name)

def is_solution_or_media(name: str) -> bool:
    """Check if name is a solution/media formulation (convenience function)."""
    return _normalizer.is_solution_or_media(name)

def convert_formula_to_name(name: str) -> str:
    """Convert chemical formula to common name (convenience function)."""
    return _normalizer.convert_formula_to_name(name)
