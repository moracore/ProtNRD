"""
Pipeline Constants (v7)

This file contains all shared, hard-coded configuration values for
the v7 pipeline. This includes invariant lists, residue contexts,
and the static (non-calculated) limits for each invariant.
"""

# --- Invariant Definitions ---
TORSION_INVARIANTS = ['tau_NA', 'tau_AC', 'tau_CN']
NON_TORSION_INVARIANTS = ['length_NA', 'length_AC', 'length_CN', 'angle_N', 'angle_A', 'angle_C']
ALL_INVARIANTS = TORSION_INVARIANTS + NON_TORSION_INVARIANTS

# Shorthand for labels (from project plan)
INVARIANT_SHORTHAND = {
    'tau_NA': '$\phi$',
    'tau_AC': '$\psi$',
    'tau_CN': '$\omega$',
    'angle_N': '$\\alpha(N)$',
    'angle_A': '$\\alpha(A)$',
    'angle_C': '$\\alpha(C)$',
    'length_NA': '$L(N)$',
    'length_AC': '$L(A)$',
    'length_CN': '$L(C)$'
}

# --- Invariant Types ---
# Helper dict to map invariants to their type
INVARIANT_TYPES = {}
for inv in TORSION_INVARIANTS:
    INVARIANT_TYPES[inv] = 'torsion'
for inv in ['angle_N', 'angle_A', 'angle_C']:
    INVARIANT_TYPES[inv] = 'angle'
for inv in ['length_NA', 'length_AC', 'length_CN']:
    INVARIANT_TYPES[inv] = 'length'

# --- Job Configuration ---
# Define resolution "levels"
RESOLUTION_LEVELS = ['level_1'] 

# Define the physical bin sizes for each type at each level
RESOLUTION_BINS = {
    'level_1': {
        'torsion': 1.0,  # degrees
        'angle':   1.0,  # degrees
        'length':  0.05  # angstroms
    }
}

RESIDUE_CONTEXTS = [
    "Any", "A", "C", "D", "E", "F", "G", "H", "I", "K", "L", 
    "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"
]

# --- Static Invariant Limits (Replaces Objective 1.2) ---
# These are used for binning 3D heatmaps and 1D histograms.
# (Using reasonable estimates based on chemical properties)
INVARIANT_LIMITS = {
    # Torsions (degrees)
    'tau_NA': {'limit_min': -180.0, 'limit_max': 180.0},
    'tau_AC': {'limit_min': -180.0, 'limit_max': 180.0},
    'tau_CN': {'limit_min': -180.0, 'limit_max': 180.0},
    
    # Angles (degrees)
    'angle_N': {'limit_min': -180.0, 'limit_max': 180.0},
    'angle_A': {'limit_min': -180.0, 'limit_max': 180.0},
    'angle_C': {'limit_min': -180.0, 'limit_max': 180.0},

    # Lengths (angstroms)
    'length_NA': {'limit_min': 1.0, 'limit_max': 2.0},
    'length_AC': {'limit_min': 1.0, 'limit_max': 2.0},
    'length_CN': {'limit_min': 1.0, 'limit_max': 2.0},
}