import os

# --- PATH CONFIGURATION ---
CURRENT_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_PKG_DIR)
DB_PATH = os.path.join(ROOT_DIR, 'proteins_v8.db')
BASE_PATH = os.environ.get('PROTNRD_BASE', '')  # e.g. '/protNRD' on server, '' locally
# --------------------------

MAX_GRAPHS = 6 

INVARIANT_ORDER = [
    'tau_NA', 'tau_AC', 'tau_CN',
    'angle_N', 'angle_A', 'angle_C',
    'length_NA', 'length_AC', 'length_CN'
]

TORSION_INVARIANTS = ['tau_NA', 'tau_AC', 'tau_CN']
NON_TORSION_INVARIANTS = ['length_NA', 'length_AC', 'length_CN', 'angle_N', 'angle_A', 'angle_C']

RESOLUTION_LEVELS = ['level_1']

RESIDUE_CONTEXTS = [
    "Any", "A", "C", "D", "E", "F", "G", "H", "I", "K", "L", 
    "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"
]

# --- UPDATED FORMAT: "Code (Name)" ---
AMINO_ACID_NAMES = {
    "Any": "Any Residue",
    "A": "A (Alanine)", "C": "C (Cysteine)", "D": "D (Aspartic Acid)",
    "E": "E (Glutamic Acid)", "F": "F (Phenylalanine)", "G": "G (Glycine) *",
    "H": "H (Histidine)", "I": "I (Isoleucine)", "K": "K (Lysine)",
    "L": "L (Leucine)", "M": "M (Methionine)", "N": "N (Asparagine)",
    "P": "P (Proline) *", "Q": "Q (Glutamine)", "R": "R (Arginine)",
    "S": "S (Serine)", "T": "T (Threonine)", "V": "V (Valine)",
    "W": "W (Tryptophan)", "Y": "Y (Tyrosine)"
}

INVARIANT_SHORTHAND = {
    'tau_NA': 'phi (φ - NᵢAᵢ)', 'tau_AC': 'psi (ψ - AᵢCᵢ)', 'tau_CN': 'omega (ω - CᵢNᵢ₊₁)',
    'angle_N': 'Angle N (N-C-A)', 'angle_A': 'Angle A (C-A-N)', 'angle_C': 'Angle C (A-N-C)',
    'length_NA': 'Length NA (N-A)', 'length_AC': 'Length AC (A-C)', 'length_CN': 'Length CN (C-N)'
}

# --- FIXED: N_RAINBOW must be a list of colors, not an integer ---
N_RAINBOW = [
    [0.0, 'rgb(0,0,200)'], [0.125, 'rgb(0,25,255)'], [0.25, 'rgb(0,152,255)'],
    [0.375, 'rgb(44,255,150)'], [0.5, 'rgb(151,255,0)'], [0.625, 'rgb(255,234,0)'],
    [0.75, 'rgb(255,111,0)'], [0.875, 'rgb(255,0,0)'], [1.0, 'rgb(0,0,0)']
]

PLOTLY_COLORSCALES = [
    'Custom Rainbow', 'Viridis', 'Plasma', 'Inferno', 'Magma', 'Cividis', 
    'Blues', 'Reds', 'Greens', 'Greys', 'YlGnBu', 'RdBu', 'Picnic', 'Rainbow', 'Portland', 'Jet', 'Hot', 'Blackbody', 'Earth', 'Electric'
]

# --- URL ENCODING MAPS ---
URL_SHORT_MAP = {
    # Invariants (3 chars)
    'tau_NA': 'phi', 'tau_AC': 'psy', 'tau_CN': 'ome',
    'angle_N': 'baN', 'angle_A': 'baA', 'angle_C': 'baC',
    'length_NA': 'lNA', 'length_AC': 'lAC', 'length_CN': 'lCN',
    
    # Views
    'graph': 'g', 'stats': 's',
    # Residues
    'Any': '+',
    # Log Scale
    True: '1', False: '0'
}

# Reverse map for decoding
URL_DECODE_MAP = {v: k for k, v in URL_SHORT_MAP.items()}