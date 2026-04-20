import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.patheffects as path_effects
import os
import numpy as np

# --- Configuration & Aesthetics ---
csv_path = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\aswani_model\validation\outputs\track_b_results_granular.csv"
output_path = r"C:\Users\me.com\Documents\engery\OpenStudio_Project\aswani_model\validation\outputs\complete_sensitivity_matrix.png"

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
        print(f"ERROR: File not found {csv_path}")
        return

    df = pd.read_csv(csv_path)

    # 1. DEFINE METHODOLOGICAL STAGES (Reviewer Defense Path)
    # We focus on the predictive lift from each AUDIT step.
    stage_map = {
        'B0':  'Naive Fused (45m Lag)',
        'B1b': 'Lag-Shift Corrected (20m)',
        'B2a': 'Optimal Density Tuning',
        'B3':  'Ventilation Synchronization',
        'B5a': 'Infiltration Refinement',
        'B5b': 'Sensible Heat Refinement',
        'B4':  'Final Golden Model'
    }

    # 2. SELECT BEST CONFIGURATION PER STAGE (Optimal Evidence)
    # We sort by CO2 RMSE as it's the most sensitive to occupancy logic.
    filtered_data = []
    for stage_id, display_name in stage_map.items():
        # Get all runs for this stage
        s_df = df[df['stage'] == stage_id].copy()
        if s_df.empty: continue
        
        # Pick the winner based on temperature + co2 aggregate score
        # (normalized to avoid scaling issues)
        s_df['acc_score'] = (s_df['co2_RMSE_TZ_NW'] / s_df['co2_RMSE_TZ_NW'].min()) + \
                            (s_df['temperature_RMSE_TZ_NW'] / s_df['temperature_RMSE_TZ_NW'].min())
        
        winner = s_df.sort_values('acc_score').iloc[0]
        winner_dict = winner.to_dict()
        winner_dict['Stage Name'] = display_name
        filtered_data.append(winner_dict)

    df_plot = pd.DataFrame(filtered_data)
    
    # 3. PREPARE PLOTTING DATA
    stages = df_plot['Stage Name']
    # Define metric groups: (RMSE_Col, Color, Label)
    metrics_cfg = [
        ('co2_RMSE_TZ_NW', '#4cc9f0', 'CO₂'),
        ('temperature_RMSE_TZ_NW', '#f72585', 'Temp'),
        ('humidity_RMSE_TZ_NW', '#4ade80', 'Humidity')
    ]

    # Create Unified Single-Panel Chart
    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Calculate Normalization Base (Naive Fused = 100%)
    baselines = {label: float(df_plot.iloc[0][col]) for col, color, label in metrics_cfg}
    
    for i, (rmse_col, color, label) in enumerate(metrics_cfg):
        rmse_data = df_plot[rmse_col]
        # Normalize to % of initial naive baseline (higher is worse)
        norm_data = (rmse_data / baselines[label]) * 100
        
        # Plot unified line
        ax.plot(stages, norm_data, color=color, marker='o', linewidth=5, markersize=16, 
                label=f'{label} (Base: {baselines[label]:.1f})', 
                path_effects=[path_effects.SimpleLineShadow(), path_effects.Normal()])
        
        # Annotate raw values on the line
        for j, (norm_val, raw_val) in enumerate(zip(norm_data, rmse_data)):
            # Offset labels for readability
            v_offset = 3 if i % 2 == 0 else -6
            ax.annotate(f'{raw_val:.2f}', (j, norm_val), 
                        textcoords="offset points", xytext=(0, 15), 
                        ha='center', fontsize=11, fontweight='bold', color=color)

    # Styling the Unified Chart
    ax.set_title('Normalized Methodology Audit: Building-Wide Accuracy Lift', fontsize=22, pad=40, fontweight='bold')
    ax.set_ylabel('Relative Error (% of Naive Baseline)', fontsize=14, fontweight='bold')
    ax.set_xlabel('Audit Optimization Stage', fontsize=14, fontweight='bold', labelpad=30)
    
    # Make X-Axis CRYSTAL CLEAR
    ax.set_xticklabels(stages, fontsize=12, fontweight='bold', rotation=0) # Keep rotation 0 if space allows
    plt.xticks(ha='center')
    
    # Grid and limits
    ax.grid(True, linestyle=':', alpha=0.15)
    ax.set_ylim(0, 110) # 100% is the baseline
    ax.axhline(100, color='white', linestyle='--', alpha=0.3, label='Naive Reference')

    # Legend
    ax.legend(loc='lower left', bbox_to_anchor=(0.02, 0.05), fontsize=12, frameon=True, facecolor='#0a0a15', edgecolor='#444')
    
    # Add a success banner
    ax.fill_between(stages, 0, 110, where=(stages == stages.iloc[-1]), color='#4ade80', alpha=0.05)
    
    plt.tight_layout(pad=5.0)
    plt.savefig(output_path, dpi=300)
    print(f"SUCCESS: Unified Methodology Matrix generated at {output_path}")

if __name__ == "__main__":
    main()
