import os
import argparse
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.cluster.hierarchy import linkage, leaves_list, fcluster
from scipy.spatial.distance import squareform

# ── Config ────────────────────────────────────────────────────────────────────
BASE_PATH   = "KETI"
DATE_RANGE  = ("2013-08-23", "2013-08-31 23:59:59")
OUTPUT_ROOT = "multi_sensor_analysis"

# ── Helper: Loading ───────────────────────────────────────────────────────────
def load_sensor(office_path, file_name, sensor_type):
    """Load a KETI sensor CSV (Unix-timestamp, value) → datetime-indexed Series."""
    path = os.path.join(office_path, file_name)
    if not os.path.isfile(path):
        return None
    try:
        df = pd.read_csv(
            path,
            header=None,
            names=["timestamp", "value"],
            skipinitialspace=True
        )
        if df.empty: return None
        
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
        df = df.set_index("datetime").sort_index()
        df = df[~df.index.duplicated(keep="first")]
        
        # Special preprocessing for PIR and Light
        if sensor_type == "pir":
            # Per user request: binary occupancy then 30min rolling max
            occupied = (df["value"] > 0).astype(int)
            # Use '30min' rolling window if index is datetime
            df["value"] = occupied.rolling("30min").max().fillna(0)
        elif sensor_type == "light":
            df["value"] = df["value"].interpolate().bfill().ffill()
            
        return df["value"]
    except Exception as e:
        print(f"  [ERROR] {path} – {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="KETI Sensor Behavioral Clustering & Plotting")
    parser.add_argument("--sensor", type=str, choices=["co2", "pir", "light"],
                        help="Sensor type to analyze (co2, pir, light)")
    args, unknown = parser.parse_known_args()
    
    # If no sensor argument is provided (e.g. running from icon), show an interactive menu
    if args.sensor is None:
        print("\n=== KETI Sensor Analysis Tool ===")
        print("Please choose a sensor to analyze:")
        print(" [1] CO2 Concentration")
        print(" [2] PIR (Motion)")
        print(" [3] Light (Lux)")
        print(" [Q] Quit")
        
        choice = input("\nEnter choice [1-3, Q]: ").strip().lower()
        if choice == "1": args.sensor = "co2"
        elif choice == "2": args.sensor = "pir"
        elif choice == "3": args.sensor = "light"
        else:
            print("Exiting.")
            return
    
    sensor_map = {
        "co2": {"file": "co2.csv", "label": "CO2 Concentration (ppm)", "cmap": "tab10", "title": "CO2"},
        "pir": {"file": "pir.csv", "label": "Motion Activity Index", "cmap": "Greens", "title": "PIR (Motion)"},
        "light": {"file": "light.csv", "label": "Illuminance (Lux)", "cmap": "YlOrRd", "title": "Light"}
    }
    
    cfg = sensor_map[args.sensor]
    output_dir = os.path.join(OUTPUT_ROOT, args.sensor)
    os.makedirs(os.path.join(output_dir, "raw"), exist_ok=True)

    print(f"\n>>> Starting {cfg['title']} Analysis <<<\n")

    # 1. Discover and Load Data
    offices = sorted([d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))])
    sensor_data = {}
    print(f"Scanning {len(offices)} offices for {cfg['file']}...")
    
    for office in offices:
        series = load_sensor(os.path.join(BASE_PATH, office), cfg["file"], args.sensor)
        if series is not None and not series.empty:
            series = series.loc[DATE_RANGE[0]:DATE_RANGE[1]]
            if not series.empty:
                sensor_data[office] = series

    if not sensor_data:
        print(f"No {args.sensor} data found in study period. Exiting.")
        return

    print(f"Loaded {len(sensor_data)} offices.\n")

    # 2. Behavioral Clustering
    print(f"Performing behavioral clustering for {args.sensor}...")
    
    office_to_cluster = {}
    unique_clusters = []

    if args.sensor == "pir":
        # RULE-BASED BEHAVIORAL CLASSIFICATION FOR PIR (Restored)
        valid_offices = []
        office_to_cluster = {}
        
        for off, s in sensor_data.items():
            # Create a "Typical Hourly Profile" (average occupancy across all days)
            typical_day = s.groupby(s.index.hour).mean()
            
            # Feature Extraction (Based on typical behavior)
            # Threshold 0.2 identifies true occupancy intensity
            active_hours = typical_day[typical_day > 0.2].index
            
            end_hour = active_hours.max() if not active_hours.empty else 0
            duration = len(active_hours)
            
            # Rule-Based Classification Logic (User Provided)
            if end_hour >= 20:
                label = "Extended Hours"
            elif duration >= 6:
                label = "Normal"
            else:
                label = "Low Occupancy"
            
            office_to_cluster[off] = label
            valid_offices.append(off)
            
        unique_clusters = ["Normal", "Extended Hours", "Low Occupancy"]
        
    elif args.sensor == "light":
        # ADVANCED BASELINE SUBTRACTION CLASSIFICATION FOR LIGHT (Option A: Rule-Based)
        print("Extracting behavioral residuals for Light (Option A)...")
        hourly_all = [s.resample("1H").mean().rename(o) for o, s in sensor_data.items()]
        hourly_df = pd.concat(hourly_all, axis=1).interpolate().bfill().ffill()
        
        # Step 2 & 3: Baseline Estimation & Residual Extraction
        baseline = hourly_df.median(axis=1)
        residual_df = hourly_df.subtract(baseline, axis=0).clip(lower=0)
        
        # Step 4: Normalization (Max scaling per office)
        norm_residual_df = residual_df.apply(
            lambda col: col / col.max() if col.max() > 0 else col,
            axis=0
        )
        
        # Step 5: Option A - Rule-Based Archetyping
        office_to_cluster = {}
        for off in hourly_df.columns:
            # All decisions MUST be based on residual behavior
            res_col = norm_residual_df[off]
            
            evening_residual = res_col.loc[res_col.index.hour >= 18].mean()
            overall_mean_residual = res_col.mean()
            
            if evening_residual > 0.20:
                label = "Extended Hours"
            elif overall_mean_residual < 0.05:
                label = "Low Occupancy"
            else:
                label = "Normal Office"
                
            office_to_cluster[off] = label
        
        unique_clusters = ["Normal Office", "Extended Hours", "Low Occupancy"]
        global_system_baseline = baseline

    else:
        # Time-series correlation clustering for CO2 
        # Resample to hourly to get similarity profiles
        hourly_all = [s.resample("1H").mean().rename(o) for o, s in sensor_data.items()]
        hourly_df = pd.concat(hourly_all, axis=1).interpolate().bfill().ffill()
        
        # normalize by office to emphasize shape
        hourly_df = hourly_df.apply(
            lambda col: (col - col.min()) / (col.max() - col.min()) if col.max() > col.min() else col * 0,
            axis=0
        )
        
        corr = hourly_df.corr().fillna(0)
        dist = 1 - corr
        dist_sym = (dist + dist.T) / 2
        np.fill_diagonal(dist_sym.values, 0)
        
        Z = linkage(squareform(dist_sym), method='ward')
        # Threshold 0.3 = Correlation > 0.7
        cluster_ids = fcluster(Z, t=0.3, criterion='distance')
        office_to_cluster = {off: str(cid) for off, cid in zip(hourly_df.columns, cluster_ids)}
        unique_clusters = sorted(list(set(office_to_cluster.values())))
    
    print(f"Detected {len(unique_clusters)} behavioral groups: {unique_clusters}")
    
    # Save behavior mapping to Local Artifact
    mapping_file = os.path.join(output_dir, f"{args.sensor}_behavior_map.md")
    with open(mapping_file, "w") as f:
        f.write(f"# {cfg['title']} Weekly Behavioral Mapping\n\n")
        f.write(f"Offices grouped by similarity in {args.sensor} patterns over the full study period.\n\n")
        f.write("| Group | Size | Office IDs |\n")
        f.write("|-------|------|------------|\n")
        for cid in unique_clusters:
            members = [off for off, c in office_to_cluster.items() if c == cid]
            f.write(f"| {cid} | {len(members)} | {', '.join(members)} |\n")
    print(f"Behavioral map saved to: {mapping_file}")

    # 3. Export Daily Tables and Annotated Plots
    print("\nGenerating daily tables and annotated charts...")
    all_days = sorted(list(set(day for s in sensor_data.values() for day in s.index.normalize().unique())))

    for day_start in all_days:
        date_str = day_start.strftime("%Y-%m-%d")
        day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
        
        # Build daily matrix
        raw_list = []
        for off in sensor_data:
            s_day = sensor_data[off].loc[day_start:day_end]
            if not s_day.empty:
                raw_list.append(s_day.rename(off))
        
        if not raw_list: continue
        df_raw = pd.concat(raw_list, axis=1)
        
        # Save CSV
        csv_path = os.path.join(output_dir, "raw", f"{args.sensor}_raw_{date_str}.csv")
        df_raw.to_csv(csv_path)

        # ── PLOT ──
        fig, ax = plt.subplots(figsize=(16, 9))
        fig.patch.set_facecolor("#0a0a0f")
        ax.set_facecolor("#12121f")
        
        # Using the modern colormaps API to avoid all deprecation warnings
        cmap = matplotlib.colormaps[cfg["cmap"]].resampled(len(unique_clusters) + 2)
        
        # Sorting and qualitative coloring by group name
        sorted_plot_offices = sorted(df_raw.columns, key=lambda x: office_to_cluster.get(x, "Unknown"))
        
        # Fixed color map for consistent archetype coloring
        colors_map = {
            "Normal": "#4cc9f0",         # Cyan/Blue for normal
            "Extended Hours": "#f72585", # Vivid pink for extended
            "Low Occupancy": "#7209b7"   # Purple for low
        }

        for off in sorted_plot_offices:
            s_plot = df_raw[off].dropna()
            if s_plot.empty: continue
            
            group_name = office_to_cluster.get(off, "Unknown")
            color = colors_map.get(group_name, "gray")
            
            ax.plot(s_plot.index, s_plot.values, marker=".", markersize=2.5, 
                    linewidth=0.8, alpha=0.7, color=color, label=f"[{group_name}] {off}")

        # Shaded Business Hours (8:00 - 18:00)
        ax.axvspan(day_start + pd.Timedelta(hours=8),
                   day_start + pd.Timedelta(hours=18),
                   color="#1a2a44", alpha=0.4, zorder=0)
        
        # If Light sensor, draw the Building System Baseline (median profile) per user feedback
        if args.sensor == "light":
            # Extract median for this specific day
            day_baseline = global_system_baseline.loc[day_start:day_end]
            if not day_baseline.empty:
                ax.plot(day_baseline.index, day_baseline.values, color="white", 
                        linestyle="--", linewidth=2.0, alpha=0.6, label="SYSTEM BASELINE (Median)")
        ax.text(day_start + pd.Timedelta(hours=13), ax.get_ylim()[1] * 0.95, 
                "BUSINESS HOURS (8:00 - 18:00)", 
                color="#4a6a94", fontsize=10, fontweight='bold', ha='center', alpha=0.8)

        # Summary Annotation
        cluster_counts = pd.Series([office_to_cluster[o] for o in df_raw.columns]).value_counts().sort_index()
        summary_text = f"{cfg['title']} Behavioral Archetypes:\n" + "\n".join([f" {name}: {count}" for name, count in cluster_counts.items()])
        ax.text(0.02, 0.98, summary_text, transform=ax.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='#1a1a2e', alpha=0.8, edgecolor='#444'),
                color='white', fontsize=9)

        # Formatting
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        ax.set_title(f"Weekly Behavioral Correlation: {cfg['title']} on {date_str}", color="white", fontsize=16, pad=20)
        ax.set_xlabel("Time of Day", color="#888", fontsize=12)
        ax.set_ylabel(cfg["label"], color="#888", fontsize=12)
        ax.tick_params(colors="#777", labelsize=10)
        ax.grid(True, color="#222", linewidth=0.5, linestyle='--')
        for s in ax.spines.values(): s.set_edgecolor("#333")
        
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), facecolor="#0a0a0f", 
                  edgecolor="#444", labelcolor="white", fontsize=8, ncol=min(3, max(1, len(df_raw.columns)//10)))
        
        plt.figtext(0.5, 0.01, f"Note: Colors represent Global Weekly Similarity Clusters based on {args.sensor} patterns.", 
                     ha="center", fontsize=9, color="#555", fontstyle='italic')

        plt.tight_layout()
        plot_path = os.path.join(output_dir, "raw", f"{args.sensor}_raw_plot_{date_str}.png")
        plt.savefig(plot_path, dpi=140, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  [DONE] {date_str}")

    print(f"\n✅ All {args.sensor.upper()} analysis tasks complete. Check {output_dir}/")

if __name__ == "__main__":
    main()
