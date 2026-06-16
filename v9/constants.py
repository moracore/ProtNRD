import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
DB_PATH = os.path.join(ROOT_DIR, 'data', 'proteins_v9_72bin.db')
DATA_DIR = os.path.join(ROOT_DIR, 'data')
DEFAULT_DB = 'proteins_v9_72bin.db'   # this app (Trimer) reads the v9-schema DB
DB_FILE_PREFIX = 'proteins_v9'        # picker only offers v9-schema DBs (avoid schema mismatch)
BASE_PATH = os.environ.get('PROTNRD_BASE', '')  # e.g. '/protNRD' on server, '' locally
MAX_GRAPHS = 6 # The number of graph panels to create

def list_db_options():
    """Dropdown options: *.db files in data/ matching this app's schema prefix."""
    try:
        files = sorted(f for f in os.listdir(DATA_DIR)
                       if f.endswith('.db') and f.startswith(DB_FILE_PREFIX))
    except OSError:
        files = []
    if DEFAULT_DB not in files and os.path.isfile(os.path.join(DATA_DIR, DEFAULT_DB)):
        files.insert(0, DEFAULT_DB)
    return [{'label': f, 'value': f} for f in files]

def resolve_db(choice):
    """Map a picker choice (bare filename) to a safe absolute path inside data/.
    Falls back to the default DB if missing/invalid; blocks path traversal."""
    if choice and choice.endswith('.db') and '/' not in choice and '\\' not in choice:
        p = os.path.join(DATA_DIR, choice)
        if os.path.isfile(p):
            return p
    return os.path.join(DATA_DIR, DEFAULT_DB)

INVARIANT_ORDER = [
    'tau_NA', 'tau_AC', 'tau_CN',
    'angle_N', 'angle_A', 'angle_C',
    'length_NA', 'length_AC', 'length_CN'
] # Ordered for the dropdowns

TORSION_INVARIANTS = ['tau_NA', 'tau_AC', 'tau_CN']
NON_TORSION_INVARIANTS = ['length_NA', 'length_AC', 'length_CN', 'angle_N', 'angle_A', 'angle_C']

# v9 Database Column Prefixes
# Maps app invariant keys to the prefix used in the 'stats' table columns
DB_COL_PREFIX_MAP = {
    'tau_NA': 'phi',
    'tau_AC': 'psi',
    'tau_CN': 'omg',
    'length_NA': 'len_N',
    'length_AC': 'len_A',
    'length_CN': 'len_C',
    'angle_N': 'ang_N',
    'angle_A': 'ang_A',
    'angle_C': 'ang_C'
}

RESIDUE_CONTEXTS = [
    "A", "C", "D", "E", "F", "G", "H", "I", "K", "L", 
    "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"
]

AMINO_ACID_NAMES = {
    "A": "A (Alanine)",
    "C": "C (Cysteine)",
    "D": "D (Aspartic Acid)",
    "E": "E (Glutamic Acid)",
    "F": "F (Phenylalanine)",
    "G": "G (Glycine)",
    "H": "H (Histidine)",
    "I": "I (Isoleucine)",
    "K": "K (Lysine)",
    "L": "L (Leucine)",
    "M": "M (Methionine)",
    "N": "N (Asparagine)",
    "P": "P (Proline)",
    "Q": "Q (Glutamine)",
    "R": "R (Arginine)",
    "S": "S (Serine)",
    "T": "T (Threonine)",
    "V": "V (Valine)",
    "W": "W (Tryptophan)",
    "Y": "Y (Tyrosin)"
}

# Mapping for constructing v9 DB keys (e.g., 'A' -> 'ALA')
ONE_TO_THREE = {
    'A': 'ALA', 'R': 'ARG', 'N': 'ASN', 'D': 'ASP', 'C': 'CYS',
    'E': 'GLU', 'Q': 'GLN', 'G': 'GLY', 'H': 'HIS', 'I': 'ILE',
    'L': 'LEU', 'K': 'LYS', 'M': 'MET', 'F': 'PHE', 'P': 'PRO',
    'S': 'SER', 'T': 'THR', 'W': 'TRP', 'Y': 'TYR', 'V': 'VAL',
    'Any': 'Any'
}

INVARIANT_SHORTHAND = {
    'tau_NA': 'phi (φ - NᵢAᵢ)',
    'tau_AC': 'psi (ψ - AᵢCᵢ)',
    'tau_CN': 'omega (ω - CᵢNᵢ₊₁)',
    'angle_N': 'Angle N (N-C-A)',
    'angle_A': 'Angle A (C-A-N)',
    'angle_C': 'Angle C (A-N-C)',
    'length_NA': 'Length NA (N-A)',
    'length_AC': 'Length AC (A-C)',
    'length_CN': 'Length CN (C-N)',
}

INVARIANT_AXIS_LABEL = {
    'tau_NA': 'phi (φ)', 'tau_AC': 'psi (ψ)', 'tau_CN': 'omega (ω)',
    'angle_N': 'Angle N', 'angle_A': 'Angle A', 'angle_C': 'Angle C',
    'length_NA': 'Length NA', 'length_AC': 'Length AC', 'length_CN': 'Length CN',
}

PLOTLY_COLORSCALES = [
    "Custom Rainbow", 
    "Magma", 
    "Viridis", 
    'Plasma',
    'RdBu',
    'Cividis',
    'YlOrRd',
    'Greys',
    'Blues',
    'Spectral'
]

N_RAINBOW = [
    [0.0, 'rgb(0,0,200)'], [0.125, 'rgb(0,25,255)'], [0.25, 'rgb(0,152,255)'],
    [0.375, 'rgb(44,255,150)'], [0.5, 'rgb(151,255,0)'], [0.625, 'rgb(255,234,0)'],
    [0.75, 'rgb(255,111,0)'], [0.875, 'rgb(255,0,0)'], [1.0, 'rgb(0,0,0)']
]