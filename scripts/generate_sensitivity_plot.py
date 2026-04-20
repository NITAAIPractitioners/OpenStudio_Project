import matplotlib.pyplot as plt
import seaborn as sns
import os

# Calculated Zonal Statistics (Mean and STD across 5 primary zones)
parameters = [
    'Occupancy Magnitude\n(First-Order)',
    'Ventilation Rate (OA)\n(Second-Order)',
    'Internal Gains (EPD)\n(Second-Order)',
    'Infiltration (ACH)\n(Third-Order)',
    'Sensible Heat Fraction\n(Negligible)'
]

means = [0.84, 0.23, 0.12, 0.02, 0.01]
stds = [0.14, 0.05, 0.03, 0.01, 0.01]

# Semantic colors: Red (1st), Orange (2nd), Green (3rd), Gray (Negligible)
colors = ['#d7191c', '#fdae61', '#fdae61', '#abdda4', '#bdbdbd']

# Plot Setup
plt.figure(figsize=(11, 7))
sns.set_style("whitegrid")
plt.rcParams.update({'font.size': 13, 'font.family': 'sans-serif'})

# Create horizontal bar chart with error bars
bars = plt.barh(parameters, means, xerr=stds, color=colors, 
                edgecolor='black', alpha=0.85, capsize=6)

# Formatting
plt.gca().invert_yaxis()  # Best at top
plt.xlabel('Normalized Sensitivity (ΔE/E ÷ Δx/x)', fontweight='bold', fontsize=14)
plt.title('Causal Error Hierarchy Based on Normalized Sensitivity Analysis', 
          fontsize=15, fontweight='bold', pad=25)
plt.xlim(0, 1.1)

# Annotate values (Mean ± STD)
for bar, m, s in zip(bars, means, stds):
    width = bar.get_width()
    plt.text(means[parameters.index(parameters[means.index(m)])] + stds[means.index(m)] + 0.02, 
             bar.get_y() + bar.get_height()/2, 
             f'{m:.2f} ± {s:.2f}', va='center', fontweight='bold', fontsize=12)

plt.tight_layout()

# Ensure figures directory exists
output_dir = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\figures"
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

output_path = os.path.join(output_dir, "sensitivity_hierarchy.png")
plt.savefig(output_path, dpi=300)
print(f"Professional sensitivity hierarchy figure saved to: {output_path}")
