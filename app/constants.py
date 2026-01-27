DB_PATH = 'proteins_v9.db'
MAX_GRAPHS = 6 # The number of graph panels to create

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
    "A": "Alanine (A)",
    "C": "Cysteine (C)",
    "D": "Aspartic Acid (D)",
    "E": "Glutamic Acid (E)",
    "F": "Phenylalanine (F)",
    "G": "Glycine (G)",
    "H": "Histidine (H)",
    "I": "Isoleucine (I)",
    "K": "Lysine (K)",
    "L": "Leucine (L)",
    "M": "Methionine (M)",
    "N": "Asparagine (N)",
    "P": "Proline (P)",
    "Q": "Glutamine (Q)",
    "R": "Arginine (R)",
    "S": "Serine (S)",
    "T": "Threonine (T)",
    "V": "Valine (V)",
    "W": "Tryptophan (W)",
    "Y": "Tyrosine (Y)"
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
    'angle_N': 'Bond Angle Nᵢ',
    'angle_A': 'Bond Angle Aᵢ',
    'angle_C': 'Bond Angle Cᵢ',
    'length_NA': 'Bond Length NᵢAᵢ',
    'length_AC': 'Bond Length AᵢCᵢ',
    'length_CN': 'Bond Length CᵢNᵢ₊₁',
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