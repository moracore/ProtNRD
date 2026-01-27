# --- Constants for v5 ---
# This file holds all shared configuration variables for the application.

DB_PATH = '/users/sggnewto/fastscratch/proteins_v5.db'
MAX_GRAPHS = 6 # The number of static graph placeholders to create

# Ordered for the dropdowns as requested
INVARIANT_ORDER = [
    'tau_NA', 'tau_AC', 'tau_CN', # Torsions (phi, psi, omega)
    'angle_N', 'angle_A', 'angle_C', # Angles
    'length_N', 'length_A', 'length_C' # Lengths
]

# Shorthand for stats display and dropdowns
INVARIANT_SHORTHAND = {
    'tau_NA': 'φ', 'tau_AC': 'ψ', 'tau_CN': 'ω',
    'angle_N': 'α(N)', 'angle_A': 'α(A)', 'angle_C': 'α(C)',
    'length_N': 'L(N)', 'length_A': 'L(A)', 'length_C': 'L(C)'
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

