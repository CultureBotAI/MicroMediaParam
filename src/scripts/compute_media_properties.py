#!/usr/bin/env python3
"""
Media Composition pH and Salinity Calculator

This script computes pH and salinity (as % NaCl equivalent) for microbial growth media
compositions using rigorous physical-chemical models.

The calculations use:
1. pH: Henderson-Hasselbalch equation with activity coefficients (Davies equation)
2. Salinity: Ionic strength and conductivity-based NaCl equivalence

Author: Generated for KG-Microbe project
"""

import numpy as np
import pandas as pd
import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
try:
    from scipy.optimize import fsolve
    SCIPY_AVAILABLE = True
except ImportError:
    print("Warning: scipy not available. pH calculation will use simplified method.")
    SCIPY_AVAILABLE = False
    
import warnings

# Suppress optimization warnings for cleaner output
warnings.filterwarnings('ignore', category=RuntimeWarning)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('media_properties.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class ChemicalProperties:
    """Chemical properties for pH and salinity calculations."""
    name: str
    molecular_weight: float
    pka_values: List[float]  # Acid dissociation constants (pKa)
    charge_states: List[int]  # Charge at each ionization state
    ion_charges: Dict[str, int]  # Individual ion charges when fully dissociated
    solubility: float = 1000.0  # g/L, assume highly soluble if not specified
    activity_coeff: float = 1.0  # Activity coefficient approximation

class MediaPropertiesCalculator:
    """
    Calculate pH and salinity of microbial growth media using physical-chemical models.
    
    Methods:
    - pH calculation via Henderson-Hasselbalch with activity corrections
    - Salinity via ionic strength and NaCl equivalence
    - Uncertainty estimation based on input precision and model limitations
    """
    
    def __init__(self):
        self.chemical_db = self._build_chemical_database()
        self.temperature = 25.0  # °C, standard lab temperature
        self.ionic_strength_cache = {}
        
    def _build_chemical_database(self) -> Dict[str, ChemicalProperties]:
        """
        Build database of chemical properties for common media components.
        
        Loads chemical properties from external TSV file for better maintainability.
        
        Data sources:
        - CRC Handbook of Chemistry and Physics
        - NIST Chemistry WebBook
        - Biochemical literature for specialized compounds
        """
        db = {}
        
        # Load from external TSV file
        properties_file = Path(__file__).parent.parent.parent / 'chemical_properties.tsv'
        
        try:
            df = pd.read_csv(properties_file, sep='\t')
            
            for _, row in df.iterrows():
                # Parse pKa values
                pka_values = []
                if pd.notna(row['pka_values']) and row['pka_values']:
                    pka_values = [float(x.strip()) for x in row['pka_values'].split(',')]
                
                # Parse charge states
                charge_states = []
                if pd.notna(row['charge_states']) and row['charge_states']:
                    charge_states = [int(x.strip()) for x in row['charge_states'].split(',')]
                
                # Parse ion charges
                ion_charges = {}
                if pd.notna(row['ion_charges']) and row['ion_charges']:
                    for ion_pair in row['ion_charges'].split(','):
                        if ':' in ion_pair:
                            ion, charge = ion_pair.strip().split(':')
                            ion_charges[ion] = int(charge)
                
                # Create ChemicalProperties object
                db[row['compound_name']] = ChemicalProperties(
                    name=row['description'] if pd.notna(row['description']) else row['compound_name'],
                    molecular_weight=float(row['molecular_weight']),
                    pka_values=pka_values,
                    charge_states=charge_states,
                    ion_charges=ion_charges,
                    solubility=float(row['solubility_g_per_L']) if pd.notna(row['solubility_g_per_L']) else 1000.0,
                    activity_coeff=float(row['activity_coefficient']) if pd.notna(row['activity_coefficient']) else 1.0
                )
                
            logger.info(f"Loaded {len(db)} chemical compounds from {properties_file}")
            
        except FileNotFoundError:
            logger.error(f"Chemical properties file not found: {properties_file}")
            logger.info("Falling back to minimal hardcoded database")
            # Minimal fallback database with just a few essential compounds
            db['nacl'] = ChemicalProperties(
                name='Sodium chloride',
                molecular_weight=58.44,
                pka_values=[],
                charge_states=[0],
                ion_charges={'Na+': 1, 'Cl-': -1},
                solubility=360.0
            )
            db['glucose'] = ChemicalProperties(
                name='Glucose',
                molecular_weight=180.16,
                pka_values=[],
                charge_states=[0],
                ion_charges={},
                solubility=909.0
            )
        except Exception as e:
            logger.error(f"Error loading chemical properties: {e}")
            logger.info("Using minimal fallback database")
        
        return db
    
    def _normalize_compound_name(self, name: str) -> str:
        """Normalize compound name for database lookup."""
        if not name:
            return ''
        
        # Convert to lowercase and remove common variations
        normalized = name.lower().strip()
        
        # Remove hydration notation
        normalized = re.sub(r'\s*[·•]\s*\d+\s*h2o', '', normalized)
        normalized = re.sub(r'\s*\.\s*\d+\s*h2o', '', normalized)
        normalized = re.sub(r'\s*x\s*\d+\s*h2o', '', normalized)
        
        # Remove stereochemistry indicators
        normalized = re.sub(r'^[dl]-', '', normalized)
        normalized = re.sub(r'^[+-]-', '', normalized)
        
        # Common name mappings
        name_mappings = {
            'sodium chloride': 'nacl',
            'table salt': 'nacl',
            'potassium chloride': 'kcl',
            'magnesium chloride': 'mgcl2',
            'calcium chloride': 'cacl2',
            'sodium sulfate': 'na2so4',
            'dipotassium phosphate': 'k2hpo4',
            'dipotassium hydrogen phosphate': 'k2hpo4',
            'potassium phosphate dibasic': 'k2hpo4',
            'monopotassium phosphate': 'kh2po4',
            'potassium dihydrogen phosphate': 'kh2po4',
            'potassium phosphate monobasic': 'kh2po4',
            'ammonium chloride': 'nh4cl',
            'iron sulfate': 'feso4',
            'ferrous sulfate': 'feso4',
            'zinc sulfate': 'znso4',
            'copper sulfate': 'cuso4',
            'cupric sulfate': 'cuso4',
            'd-glucose': 'glucose',
            'dextrose': 'glucose',
            'l-glycine': 'glycine',
            'l-alanine': 'alanine',
            # Additional mappings for common unmapped compounds
            'na malate': 'sodium_malate',
            'sodium malate': 'sodium_malate',
            'na2-fumarate': 'disodium_fumarate',
            'na2 fumarate': 'disodium_fumarate',
            'disodium fumarate': 'disodium_fumarate',
            'na-formate': 'sodium_formate',
            'na formate': 'sodium_formate',
            'sodium formate': 'sodium_formate',
            'na acetate': 'sodium_acetate',
            'na-acetate': 'sodium_acetate',
            'trypticase peptone': 'peptone_mix',
            'peptone': 'peptone_mix',
            'yeast extract': 'yeast_extract'
        }
        
        if normalized in name_mappings:
            normalized = name_mappings[normalized]
        
        return normalized
    
    def _estimate_compound_properties(self, compound_name: str) -> Optional[ChemicalProperties]:
        """
        Estimate chemical properties for unmapped compounds using pattern recognition.
        
        This method uses chemical naming patterns to infer basic properties for
        compounds not in the database, particularly focusing on:
        - Sodium salts (contribute Na+ ions)
        - Organic acids and their salts
        - Common buffer systems
        
        Args:
            compound_name: Original compound name
            
        Returns:
            ChemicalProperties object with estimated values, or None if unable to estimate
        """
        name_lower = compound_name.lower().strip()
        
        # Pattern matching for sodium salts
        if any(pattern in name_lower for pattern in ['na ', 'sodium ', 'na-', 'na2-']):
            # Estimate based on common sodium salt patterns
            if 'na2-' in name_lower or 'disodium' in name_lower:
                # Disodium salt (2 Na+ per molecule)
                return ChemicalProperties(
                    name=f"Estimated disodium salt: {compound_name}",
                    molecular_weight=200.0,  # Generic estimate
                    pka_values=[4.0],  # Typical weak acid
                    charge_states=[-2, -1, 0],
                    ion_charges={'Na+': 1, 'Anion2-': -2},
                    solubility=500.0,
                    activity_coeff=0.9
                )
            else:
                # Monosodium salt (1 Na+ per molecule)
                return ChemicalProperties(
                    name=f"Estimated sodium salt: {compound_name}",
                    molecular_weight=150.0,  # Generic estimate
                    pka_values=[4.5],  # Typical weak acid
                    charge_states=[-1, 0],
                    ion_charges={'Na+': 1, 'Anion-': -1},
                    solubility=400.0,
                    activity_coeff=0.9
                )
        
        # Pattern matching for potassium salts
        elif any(pattern in name_lower for pattern in ['k ', 'potassium ', 'k-', 'k2-']):
            if 'k2-' in name_lower or 'dipotassium' in name_lower:
                return ChemicalProperties(
                    name=f"Estimated dipotassium salt: {compound_name}",
                    molecular_weight=220.0,
                    pka_values=[4.0],
                    charge_states=[-2, -1, 0],
                    ion_charges={'K+': 1, 'Anion2-': -2},
                    solubility=450.0,
                    activity_coeff=0.9
                )
            else:
                return ChemicalProperties(
                    name=f"Estimated potassium salt: {compound_name}",
                    molecular_weight=170.0,
                    pka_values=[4.5],
                    charge_states=[-1, 0],
                    ion_charges={'K+': 1, 'Anion-': -1},
                    solubility=350.0,
                    activity_coeff=0.9
                )
        
        # Pattern matching for chloride salts
        elif any(pattern in name_lower for pattern in ['chloride', 'hcl', ' cl ']):
            # Extract cation information if possible
            if any(cation in name_lower for cation in ['mg', 'magnesium']):
                return ChemicalProperties(
                    name=f"Estimated magnesium chloride: {compound_name}",
                    molecular_weight=120.0,
                    pka_values=[],
                    charge_states=[0],
                    ion_charges={'Mg2+': 2, 'Cl-': -1},
                    solubility=600.0
                )
            elif any(cation in name_lower for cation in ['ca', 'calcium']):
                return ChemicalProperties(
                    name=f"Estimated calcium chloride: {compound_name}",
                    molecular_weight=140.0,
                    pka_values=[],
                    charge_states=[0],
                    ion_charges={'Ca2+': 2, 'Cl-': -1},
                    solubility=700.0
                )
            else:
                # Generic monovalent chloride
                return ChemicalProperties(
                    name=f"Estimated chloride salt: {compound_name}",
                    molecular_weight=100.0,
                    pka_values=[],
                    charge_states=[0],
                    ion_charges={'Cation+': 1, 'Cl-': -1},
                    solubility=300.0
                )
        
        # Pattern matching for sulfate salts
        elif any(pattern in name_lower for pattern in ['sulfate', 'sulphate', 'so4']):
            return ChemicalProperties(
                name=f"Estimated sulfate salt: {compound_name}",
                molecular_weight=180.0,
                pka_values=[],
                charge_states=[0],
                ion_charges={'Cation2+': 2, 'SO42-': -2},
                solubility=250.0
            )
        
        # Pattern matching for organic acids
        elif any(pattern in name_lower for pattern in ['acid', 'ate']):
            # Distinguish between acids and their salts
            if name_lower.endswith('ate'):
                # Salt of organic acid
                return ChemicalProperties(
                    name=f"Estimated organic acid salt: {compound_name}",
                    molecular_weight=160.0,
                    pka_values=[4.0],
                    charge_states=[-1, 0],
                    ion_charges={'Cation+': 1, 'Anion-': -1},
                    solubility=300.0,
                    activity_coeff=0.85
                )
            else:
                # Free organic acid
                return ChemicalProperties(
                    name=f"Estimated organic acid: {compound_name}",
                    molecular_weight=140.0,
                    pka_values=[4.5],
                    charge_states=[-1, 0],
                    ion_charges={'H+': 1, 'Anion-': -1},
                    solubility=200.0,
                    activity_coeff=0.8
                )
        
        # Pattern matching for complex biological extracts
        elif any(pattern in name_lower for pattern in ['extract', 'peptone', 'hydrolysate', 'broth']):
            return ChemicalProperties(
                name=f"Estimated biological extract: {compound_name}",
                molecular_weight=180.0,  # Average for amino acids/peptides
                pka_values=[2.5, 9.0],  # Typical amino/carboxyl groups
                charge_states=[-1, 0, 1],
                ion_charges={'COO-': -1, 'NH3+': 1},
                solubility=250.0,
                activity_coeff=0.6  # Complex mixture, reduced activity
            )
        
        # If no pattern matches, return None (cannot estimate)
        return None
    
    def _davies_activity_coefficient(self, charge: int, ionic_strength: float) -> float:
        """
        Calculate activity coefficient using Davies equation.
        
        Davies equation: log(γ) = -A * z² * (√I / (1 + √I) - 0.3 * I)
        where A = 0.5115 at 25°C for water
        
        Args:
            charge: Ion charge
            ionic_strength: Ionic strength (M)
            
        Returns:
            Activity coefficient
        """
        if charge == 0:
            return 1.0
        
        A = 0.5115  # Debye-Hückel constant at 25°C
        sqrt_I = np.sqrt(ionic_strength)
        
        log_gamma = -A * charge**2 * (sqrt_I / (1 + sqrt_I) - 0.3 * ionic_strength)
        
        return 10**log_gamma
    
    def _calculate_ionic_strength(self, composition: List[Dict]) -> float:
        """
        Calculate ionic strength of the solution.
        
        I = 0.5 * Σ(ci * zi²)
        where ci is concentration (M) and zi is charge
        
        Args:
            composition: List of composition dictionaries
            
        Returns:
            Ionic strength (M)
        """
        ionic_strength = 0.0
        
        for comp in composition:
            original_name = comp.get('compound', '')
            compound_name = self._normalize_compound_name(original_name)
            concentration_gl = comp.get('g_l', 0) or comp.get('value', 0) or 0
            
            if not concentration_gl:
                continue
            
            # Try to get properties from database
            if compound_name in self.chemical_db:
                props = self.chemical_db[compound_name]
            else:
                # Try to estimate properties using pattern recognition
                props = self._estimate_compound_properties(original_name)
                if props is None:
                    logger.debug(f"Cannot estimate properties for ionic strength: {original_name}")
                    continue
            
            # Convert g/L to M
            concentration_M = concentration_gl / props.molecular_weight
            
            # Add contribution to ionic strength
            for ion, charge in props.ion_charges.items():
                if 'Cl-' in ion:
                    # Handle cases where multiple Cl- ions per formula unit
                    if compound_name in ['mgcl2', 'cacl2']:
                        ion_concentration = concentration_M * 2
                    else:
                        ion_concentration = concentration_M
                elif compound_name in ['na2so4'] and 'Na+' in ion:
                    ion_concentration = concentration_M * 2
                else:
                    ion_concentration = concentration_M
                
                ionic_strength += 0.5 * ion_concentration * charge**2
        
        return max(ionic_strength, 1e-7)  # Minimum to avoid division by zero
    
    def _calculate_ph_henderson_hasselbalch(self, composition: List[Dict]) -> Tuple[float, float]:
        """
        Calculate pH using Henderson-Hasselbalch equation with activity corrections.
        
        For each acid-base pair:
        pH = pKa + log([A-]/[HA]) + log(γA-/γHA)
        
        Args:
            composition: List of composition dictionaries
            
        Returns:
            Tuple of (pH, uncertainty)
        """
        ionic_strength = self._calculate_ionic_strength(composition)
        
        # Start with pure water assumption
        h_concentration = 1e-7  # Initial guess: neutral pH
        oh_concentration = 1e-7
        
        # Collect all acid-base equilibria
        equilibria = []
        
        for comp in composition:
            original_name = comp.get('compound', '')
            compound_name = self._normalize_compound_name(original_name)
            concentration_gl = comp.get('g_l', 0) or comp.get('value', 0) or 0
            
            if not concentration_gl:
                continue
            
            # Try to get properties from database
            if compound_name in self.chemical_db:
                props = self.chemical_db[compound_name]
            else:
                # Try to estimate properties using pattern recognition
                props = self._estimate_compound_properties(original_name)
                if props is None:
                    logger.debug(f"Cannot estimate properties for pH calculation: {original_name}")
                    continue
            
            concentration_M = concentration_gl / props.molecular_weight
            
            # Add equilibria for compounds with pKa values
            if props.pka_values:
                equilibria.append({
                    'concentration': concentration_M,
                    'pka_values': props.pka_values,
                    'charge_states': props.charge_states,
                    'name': compound_name,
                    'is_estimated': compound_name not in self.chemical_db
                })
        
        if not equilibria:
            # No acid-base components, assume neutral with small uncertainty
            return 7.0, 0.5
        
        def ph_equation(log_h):
            """Equation to solve for pH considering all equilibria."""
            h_conc = 10**(-log_h)
            charge_balance = h_conc - 1e-14/h_conc  # H+ - OH-
            
            for eq in equilibria:
                total_conc = eq['concentration']
                pka_vals = eq['pka_values']
                
                # Calculate alpha values (fraction in each form)
                alpha_values = self._calculate_alpha_fractions(h_conc, pka_vals)
                
                # Add charge contribution
                for i, charge in enumerate(eq['charge_states']):
                    if i < len(alpha_values):
                        gamma = self._davies_activity_coefficient(charge, ionic_strength)
                        charge_balance += charge * alpha_values[i] * total_conc * gamma
            
            return charge_balance
        
        if SCIPY_AVAILABLE:
            try:
                # Solve for pH using scipy
                ph_solution = fsolve(ph_equation, 7.0)[0]
                ph = max(0.5, min(14.0, ph_solution))  # Constrain to reasonable range
                
                # Estimate uncertainty based on ionic strength and number of components
                uncertainty = 0.1 + 0.05 * len(equilibria) + 0.1 * np.sqrt(ionic_strength)
                uncertainty = min(uncertainty, 1.0)  # Cap at 1 pH unit
                
            except:
                # Fallback to simple weighted average of pKa values
                logger.warning("pH calculation failed, using pKa average estimate")
                ph, uncertainty = self._fallback_ph_calculation(equilibria)
        else:
            # Use simplified method when scipy is not available
            ph, uncertainty = self._fallback_ph_calculation(equilibria)
        
        return ph, uncertainty
    
    def _fallback_ph_calculation(self, equilibria: List[Dict]) -> Tuple[float, float]:
        """
        Simplified pH calculation when scipy is not available.
        Uses weighted average of pKa values and Henderson-Hasselbalch approximation.
        """
        if not equilibria:
            return 7.0, 1.0
        
        # Calculate concentration-weighted average pKa
        pka_sum = 0
        weight_sum = 0
        buffer_strength = 0
        
        for eq in equilibria:
            concentration = eq['concentration']
            pka_values = eq['pka_values']
            
            # Weight pKa values by concentration
            for pka in pka_values:
                pka_sum += pka * concentration
                weight_sum += concentration
                
                # Estimate buffer strength (higher near pKa)
                buffer_strength += concentration * np.exp(-abs(7.0 - pka))
        
        if weight_sum > 0:
            avg_pka = pka_sum / weight_sum
            
            # Simple Henderson-Hasselbalch assumption: assume equal acid/base forms
            # pH ≈ pKa when [A-] = [HA]
            ph = avg_pka
            
            # Adjust slightly toward neutral for complex mixtures
            if len(equilibria) > 1:
                ph = 0.7 * ph + 0.3 * 7.0  # Blend with neutral
            
            # Estimate uncertainty based on buffer strength and complexity
            uncertainty = 0.5  # Base uncertainty for simplified method
            uncertainty += 0.1 * len(equilibria)  # More uncertainty for complex mixtures
            
            if buffer_strength < 0.001:
                uncertainty += 0.3  # Poor buffering increases uncertainty
            
            uncertainty = min(uncertainty, 1.5)  # Cap uncertainty
            
        else:
            ph = 7.0
            uncertainty = 1.0
        
        ph = max(1.0, min(13.0, ph))  # Constrain to reasonable range
        
        return ph, uncertainty
    
    def _calculate_alpha_fractions(self, h_concentration: float, pka_values: List[float]) -> List[float]:
        """
        Calculate alpha fractions for polyprotic acid/base.
        
        α₀ = [H+]ⁿ / D
        α₁ = K₁[H+]ⁿ⁻¹ / D
        ...
        where D = [H+]ⁿ + K₁[H+]ⁿ⁻¹ + K₁K₂[H+]ⁿ⁻² + ...
        """
        if not pka_values:
            return [1.0]
        
        ka_values = [10**(-pka) for pka in pka_values]
        n = len(ka_values)
        
        # Calculate denominator terms
        terms = []
        h_power = h_concentration**n
        terms.append(h_power)
        
        for i in range(n):
            h_power /= h_concentration
            ka_product = 1.0
            for j in range(i + 1):
                ka_product *= ka_values[j]
            terms.append(ka_product * h_power)
        
        denominator = sum(terms)
        
        # Calculate alpha fractions
        alphas = [term / denominator for term in terms]
        
        return alphas
    
    def _calculate_salinity_nacl_equivalent(self, composition: List[Dict]) -> Tuple[float, float]:
        """
        Calculate salinity as NaCl equivalent based on ionic strength.
        
        Uses the relationship between ionic strength and conductivity,
        then converts to NaCl equivalent mass percentage.
        
        Args:
            composition: List of composition dictionaries
            
        Returns:
            Tuple of (salinity_percent, uncertainty)
        """
        ionic_strength = self._calculate_ionic_strength(composition)
        
        # Convert ionic strength to conductivity (empirical relationship)
        # κ ≈ 0.013 * I^0.9 (S/m) for dilute solutions at 25°C
        conductivity = 0.013 * (ionic_strength**0.9)
        
        # Convert conductivity to NaCl equivalent
        # For NaCl: κ = 0.0126 * C_NaCl (S/m) where C_NaCl is in g/L
        nacl_equivalent_gl = conductivity / 0.0126
        
        # Convert to mass percentage (assuming 1 L ≈ 1 kg for dilute solutions)
        # % NaCl = (g NaCl / g solution) * 100
        # For 1 L solution ≈ 1000 g water + dissolved salts
        total_dissolved_mass = sum([
            comp.get('g_l', 0) or comp.get('value', 0) or 0 
            for comp in composition
        ])
        
        solution_mass = 1000 + total_dissolved_mass  # g
        salinity_percent = (nacl_equivalent_gl / solution_mass) * 100
        
        # Estimate uncertainty
        # Higher uncertainty for:
        # - Very low ionic strength (measurement limitations)
        # - Complex ionic mixtures (non-NaCl ions behave differently)
        uncertainty = 0.01  # Base uncertainty (0.01%)
        
        if ionic_strength < 0.001:
            uncertainty += 0.005  # Additional uncertainty for very dilute solutions
        
        # Count non-NaCl ionic compounds
        non_nacl_ions = 0
        for comp in composition:
            compound_name = self._normalize_compound_name(comp.get('compound', ''))
            if compound_name in self.chemical_db and compound_name != 'nacl':
                props = self.chemical_db[compound_name]
                if props.ion_charges:
                    non_nacl_ions += 1
        
        uncertainty += non_nacl_ions * 0.005  # Additional uncertainty for complex mixtures
        uncertainty = min(uncertainty, 0.1)  # Cap at 0.1%
        
        return salinity_percent, uncertainty
    
    def analyze_composition(self, composition_data: Union[str, List[Dict]]) -> Dict:
        """
        Analyze a media composition and compute pH and salinity.
        
        Args:
            composition_data: Either JSON string or list of composition dictionaries
            
        Returns:
            Dictionary with pH, salinity, and related properties
        """
        if isinstance(composition_data, str):
            try:
                composition = json.loads(composition_data)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                return self._error_result("Invalid JSON format")
        else:
            composition = composition_data
        
        if not isinstance(composition, list):
            return self._error_result("Composition must be a list of components")
        
        # Calculate properties
        try:
            ph, ph_uncertainty = self._calculate_ph_henderson_hasselbalch(composition)
            salinity, salinity_uncertainty = self._calculate_salinity_nacl_equivalent(composition)
            ionic_strength = self._calculate_ionic_strength(composition)
            
            # Additional properties
            total_dissolved_solids = sum([
                comp.get('g_l', 0) or comp.get('value', 0) or 0 
                for comp in composition
            ])
            
            # Count recognized vs estimated vs unrecognized compounds
            recognized_compounds = 0
            estimated_compounds = 0
            total_compounds = len(composition)
            
            recognized_list = []
            estimated_list = []
            unaccounted_list = []
            
            for comp in composition:
                original_name = comp.get('compound', '')
                compound_name = self._normalize_compound_name(original_name)
                
                if compound_name in self.chemical_db:
                    recognized_compounds += 1
                    recognized_list.append(original_name)
                elif self._estimate_compound_properties(original_name) is not None:
                    estimated_compounds += 1
                    estimated_list.append(original_name)
                else:
                    unaccounted_list.append(original_name)
            
            results = {
                'ph': {
                    'value': round(ph, 2),
                    'uncertainty': round(ph_uncertainty, 2),
                    'range': [round(ph - ph_uncertainty, 2), round(ph + ph_uncertainty, 2)],
                    'confidence': 'high' if ph_uncertainty < 0.3 else 'medium' if ph_uncertainty < 0.7 else 'low'
                },
                'salinity': {
                    'percent_nacl': round(salinity, 4),
                    'uncertainty': round(salinity_uncertainty, 4),
                    'range': [round(max(0, salinity - salinity_uncertainty), 4), 
                             round(salinity + salinity_uncertainty, 4)],
                    'confidence': 'high' if salinity_uncertainty < 0.02 else 'medium' if salinity_uncertainty < 0.05 else 'low'
                },
                'ionic_strength': {
                    'value': round(ionic_strength, 6),
                    'unit': 'M'
                },
                'total_dissolved_solids': {
                    'value': round(total_dissolved_solids, 2),
                    'unit': 'g/L'
                },
                'analysis_quality': {
                    'compounds_recognized': f"{recognized_compounds}/{total_compounds}",
                    'compounds_estimated': f"{estimated_compounds}/{total_compounds}",
                    'compounds_unaccounted': f"{len(unaccounted_list)}/{total_compounds}",
                    'total_coverage_rate': round((recognized_compounds + estimated_compounds) / max(total_compounds, 1) * 100, 1),
                    'recognition_rate': round(recognized_compounds / max(total_compounds, 1) * 100, 1),
                    'estimation_rate': round(estimated_compounds / max(total_compounds, 1) * 100, 1),
                    'calculation_method': 'Henderson-Hasselbalch with Davies activity coefficients and pattern-based estimation'
                },
                'compound_details': {
                    'recognized_compounds': recognized_list,
                    'estimated_compounds': estimated_list,
                    'unaccounted_compounds': unaccounted_list
                },
                'notes': self._generate_analysis_notes(composition, recognized_compounds, estimated_compounds, total_compounds)
            }
            
            return results
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return self._error_result(f"Calculation error: {str(e)}")
    
    def _error_result(self, message: str) -> Dict:
        """Return standardized error result."""
        return {
            'error': message,
            'ph': {'value': None, 'uncertainty': None, 'confidence': 'none'},
            'salinity': {'percent_nacl': None, 'uncertainty': None, 'confidence': 'none'}
        }
    
    def _generate_analysis_notes(self, composition: List[Dict], recognized: int, estimated: int, total: int) -> List[str]:
        """Generate analysis notes and warnings."""
        notes = []
        
        unaccounted = total - recognized - estimated
        
        if estimated > 0:
            notes.append(f"Note: {estimated} compounds estimated using pattern recognition (Na salts, organic acids, etc.)")
            notes.append("Estimated compounds contribute to pH/salinity but with increased uncertainty")
        
        if unaccounted > 0:
            notes.append(f"Warning: {unaccounted} compounds not accounted for in calculations")
            notes.append("Unaccounted compounds may significantly affect actual pH and salinity")
        
        # Check for buffers (both recognized and estimated)
        buffer_compounds = ['tris', 'hepes', 'k2hpo4', 'kh2po4', 'peptone_mix', 'yeast_extract']
        has_buffer = False
        estimated_buffers = []
        
        for comp in composition:
            original_name = comp.get('compound', '')
            compound_name = self._normalize_compound_name(original_name)
            if compound_name in buffer_compounds:
                has_buffer = True
                if compound_name in ['peptone_mix', 'yeast_extract']:
                    estimated_buffers.append(original_name)
        
        if has_buffer:
            if estimated_buffers:
                notes.append(f"Buffer system detected including estimated buffers: {', '.join(estimated_buffers)}")
            else:
                notes.append("Buffer system detected - pH calculation includes buffering capacity")
        else:
            notes.append("No major buffer detected - pH may be less stable")
        
        # Check for sodium compounds specifically
        sodium_compounds = []
        for comp in composition:
            original_name = comp.get('compound', '').lower()
            if any(pattern in original_name for pattern in ['na ', 'sodium', 'na-', 'na2-']):
                sodium_compounds.append(comp.get('compound', ''))
        
        if sodium_compounds:
            notes.append(f"Sodium-containing compounds detected: {len(sodium_compounds)} compounds contribute to salinity")
        
        # Check for high ionic strength
        ionic_strength = self._calculate_ionic_strength(composition)
        if ionic_strength > 0.1:
            notes.append("High ionic strength - activity coefficient corrections applied")
        elif ionic_strength < 0.001:
            notes.append("Low ionic strength - results may have higher uncertainty")
        
        return notes

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Calculate pH and salinity of media compositions')
    parser.add_argument('input_file', help='JSON file containing media composition')
    parser.add_argument('-o', '--output', help='Output file for results (optional)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load composition data
    try:
        with open(args.input_file, 'r') as f:
            composition_data = json.load(f)
    except Exception as e:
        logger.error(f"Error loading input file: {e}")
        return 1
    
    # Initialize calculator and analyze
    calculator = MediaPropertiesCalculator()
    results = calculator.analyze_composition(composition_data)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to {args.output}")
    else:
        print(json.dumps(results, indent=2))
    
    return 0

if __name__ == "__main__":
    exit(main())