## Pipeline Constants v0.9
## Optimized for strict 3-mer (triplet) analysis.

# Core Invariants
TORSION_INVARIANTS = ['tau_NA', 'tau_AC', 'tau_CN']
LENGTH_INVARIANTS = ['length_NA', 'length_AC', 'length_CN']
ANGLE_INVARIANTS = ['angle_N', 'angle_A', 'angle_C']

# Map to standard nomenclature
INVARIANT_NAMES = {
    'tau_NA': 'phi',
    'tau_AC': 'psi',
    'tau_CN': 'omega',
    'length_NA': 'L(N-CA)',
    'length_AC': 'L(CA-C)',
    'length_CN': 'L(C-N)',
    'angle_N': 'alpha(N)',
    'angle_A': 'alpha(CA)',
    'angle_C': 'alpha(C)'
}

THR_FREQUENCY = 0  # Minimum frequency required to generate a 3D heatmap

RESOLUTION_BINS = {
    'level_1': {
        'torsion': 1.0  # 1.0 degree bins for heatmaps
    }
}

# Limits for Heatmap Generation
INVARIANT_LIMITS = {
    'tau_NA': (-180.0, 180.0),
    'tau_AC': (-180.0, 180.0),
    'tau_CN': (-180.0, 180.0)
}

# Shorthand for UI/Latex Rendering
INVARIANT_SHORTHAND = {
    'tau_NA': '$\phi$',
    'tau_AC': '$\psi$',
    'tau_CN': '$\omega$',
    'length_NA': '$L_N$',
    'length_AC': '$L_A$',
    'length_CN': '$L_C$',
    'angle_N': '$\\alpha_N$',
    'angle_A': '$\\alpha_A$',
    'angle_C': '$\\alpha_C$'
}

# The 20 standard Amino Acids (for reference/sorting)
AMINO_ACIDS = [
    "A", "C", "D", "E", "F", "G", "H", "I", "K", "L", 
    "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y"
]