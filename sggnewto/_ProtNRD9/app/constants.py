import os

## Pipeline Constants v0.9
## Updated for 3-mer Triplet Analysis and 77-Metric Schema

# FIX: Look for DB in the CURRENT directory (app/), not the parent
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'proteins_v9.db')

MAX_GRAPHS = 6 

# The full set of 9 invariants per residue
TORSION_INVARIANTS = ['tau_NA', 'tau_AC', 'tau_CN']
LENGTH_INVARIANTS = ['length_NA', 'length_AC', 'length_CN']
ANGLE_INVARIANTS = ['angle_N', 'angle_A', 'angle_C']

# UI now only allows selecting Torsions for the axes
DROPDOWN_ORDER = TORSION_INVARIANTS 

# Shorthand for UI rendering
INVARIANT_SHORTHAND = {
    'tau_NA': 'phi (φ)',
    'tau_AC': 'psi (ψ)',
    'tau_CN': 'omega (ω)',
    'angle_N': 'Angle N',
    'angle_A': 'Angle CA',
    'angle_C': 'Angle C',
    'length_NA': 'Length N-CA',
    'length_AC': 'Length CA-C',
    'length_CN': 'Length C-N',
}

# Mapping for the 2D Global Profile
G2D_METRICS = {
    'phi_psi_mean_phi': '2D Mean phi',
    'phi_psi_mean_psi': '2D Mean psi',
    'phi_psi_corr': 'Circular Correlation (ρcc)',
    'phi_psi_R2D': 'Joint Rigidity (R2D)',
    'phi_psi_peak_phi': '2D Peak phi',
    'phi_psi_peak_psi': '2D Peak psi',
    'phi_psi_peak_f': 'Peak 2D Frequency',
    'phi_psi_mean_f': 'Frequency at 2D Mean'
}

AMINO_ACIDS = [
    "A", "C", "D", "E", "F", "G", "H", "I", "K", "L", 
    "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"
]

AMINO_ACID_NAMES = {aa: aa for aa in AMINO_ACIDS}

PLOTLY_COLORSCALES = [
    "Custom Rainbow", "Magma", "Viridis", "Plasma", "RdBu", "Spectral"
]

N_RAINBOW = [
    [0.0, 'rgb(0,0,200)'], [0.125, 'rgb(0,25,255)'], [0.25, 'rgb(0,152,255)'],
    [0.375, 'rgb(44,255,150)'], [0.5, 'rgb(151,255,0)'], [0.625, 'rgb(255,234,0)'],
    [0.75, 'rgb(255,111,0)'], [0.875, 'rgb(255,0,0)'], [1.0, 'rgb(0,0,0)']
]