import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# --- Configuration ---
csv_path = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\aswani_model\validation\outputs\track_b_results_granular.csv"
output_path = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\aswani_model\validation\outputs\occupancy_error_relation.png"

# Classical Styling (Academic White Background)
plt.style.use('default')
plt.rcParams.update({
    "font.family": "serif",
    "axes.grid": True,
    "grid.linestyle": ":",
    "grid.alpha": 0.5,
    "legend.frameon": True,
    "legend.facecolor": "white",
    "legend.edgecolor": "black"
})

def main():
    if not os.path.exists(csv_path):
        print("CSV missing.")
        return

    df = pd.read_csv(csv_path)
    
    # Filter out ASHRAE if present, or just use everything to show the contrast
    # The user/teacher wants to see the relation.
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    metrics = [
        ('Avg_Sim_Occ_TZ_NW', 'co2_RMSE_TZ_NW', '#4cc9f0', 'CO₂ RMSE (ppm)'),
        ('Avg_Sim_Occ_TZ_NW', 'temperature_RMSE_TZ_NW', '#f72585', 'Temperature RMSE (°C)')
    ]
    
    for i, (x_col, y_col, color, label) in enumerate(metrics):
        ax = axes[i]
        
        # Draw regression line
        sns.regplot(data=df, x=x_col, y=y_col, ax=ax, scatter=True, 
                    color=color, scatter_kws={'s': 100, 'alpha':0.6, 'edgecolor': 'white'},
                    line_kws={'color': 'white', 'alpha': 0.4, 'linestyle': '--'})
        
        # Label points by stage
        for _, row in df.iterrows():
            ax.text(row[x_col], row[y_col], f" {row['stage']}", color='#aaa', fontsize=8, alpha=0.8)

        ax.set_title(f'Occupancy Pressure vs {label}', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('Average Zone Population (Occupants)', fontsize=11)
        ax.set_ylabel(label, fontsize=11)
        ax.grid(True, alpha=0.1)

    plt.suptitle('Predictive Integrity Audit: Error vs Occupancy Load', fontsize=18, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"SUCCESS: Relationship Map generated at {output_path}")

if __name__ == "__main__":
    main()
