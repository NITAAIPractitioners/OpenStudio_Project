import os
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# If scipy is missing, we'll gracefully fallback
try:
    from scipy.cluster.hierarchy import linkage, leaves_list, fcluster
    from scipy.spatial.distance import squareform
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Warning: scipy not installed, grouping similarly will be skipped. Columns will be grouped alphabetically.")

# ── Config ────────────────────────────────────────────────────────────────────
BASE_PATH   = "KETI"
DATE_RANGE  = ("2013-08-23", "2013-08-31 23:59:59")
OUTPUT_DIR  = "office_csv_tables"

for res in ["raw", "10min", "hourly"]:
    os.makedirs(os.path.join(OUTPUT_DIR, res), exist_ok=True)

# ── 1. Load Data ──────────────────────────────────────────────────────────────
def load_sensor(office_path, file_name):
    path = os.path.join(office_path, file_name)
    if not os.path.isfile(path): return None
    try:
        df = pd.read_csv(path, header=None, names=["timestamp", "value"], skipinitialspace=True)
    except Exception:
        return None
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")
    df = df.set_index("datetime").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df["value"]

print("1. Loading raw CO2 data for all offices...")
offices = sorted([d for d in os.listdir(BASE_PATH) if os.path.isdir(os.path.join(BASE_PATH, d))])
co2_data = {}
for office in offices:
    raw = load_sensor(os.path.join(BASE_PATH, office), "co2.csv")
    if raw is not None and not raw.empty:
        raw = raw.loc[DATE_RANGE[0]:DATE_RANGE[1]]
        if not raw.empty:
            co2_data[office] = raw

print(f"Loaded {len(co2_data)} offices.")

# ── 2. Group Similar Offices ──────────────────────────────────────────────────
print("\n2. Grouping similar offices together...")
hourly_all = [s.resample("1H").mean().rename(o) for o, s in co2_data.items()]
hourly_df = pd.concat(hourly_all, axis=1).fillna(0)

if HAS_SCIPY and hourly_df.shape[1] > 1:
    corr = hourly_df.corr().fillna(0)
    dist = 1 - corr
    dist_condensed = squareform((dist + dist.T) / 2 - np.diag(np.diag(dist)))
    try:
        Z = linkage(dist_condensed, 'ward')
        order = leaves_list(Z)
        sorted_offices = [hourly_df.columns[i] for i in order]
        
        # --- NEW: Assign Global Clusters based on similarity ---
        # Distance threshold of 0.3 means correlation > 0.7
        cluster_ids = fcluster(Z, t=0.3, criterion='distance')
        office_to_cluster = {off: cid for off, cid in zip(hourly_df.columns, cluster_ids)}
        unique_clusters = sorted(list(set(cluster_ids)))
        print(f"Detected {len(unique_clusters)} behavioral groups over the week.")
        
        # Save behavior groups to a simple local file for verification
        with open("behavior_groups_output.md", "w") as f:
            f.write("# Detected Behavioral Groups (Weekly Correlation > 0.7)\n\n")
            f.write("| Group | Size | Offices |\n")
            f.write("|---|---|---|\n")
            for cid in unique_clusters:
                members = [off for off, c in office_to_cluster.items() if c == cid]
                f.write(f"| {cid} | {len(members)} | {', '.join(members)} |\n")
        
        # Also try to write the artifact if possible
        artifact_path = r"C:\Users\me.com\.gemini\antigravity\brain\4b64d3a1-f78e-4533-832c-54c9e7a1ad6f\office_groups.md"
        try:
            with open(artifact_path, "w") as f:
                f.write("# Office Group Assignments\n\n- Based on Weekly CO2 Correlation\n\n")
                for cid in unique_clusters:
                    members = [off for off, c in office_to_cluster.items() if c == cid]
                    f.write(f"### Group {cid} ({len(members)} offices)\n")
                    f.write(f"- {', '.join(members)}\n\n")
        except: pass
            
        print(f"Successfully grouping recorded to local behavior_groups_output.md")
    except Exception as e:
        print(f"Clustering failed ({e}), falling back to alphabetical.")
        sorted_offices = sorted(co2_data.keys())
        office_to_cluster = {off: 1 for off in sorted_offices}
else:
    sorted_offices = sorted(co2_data.keys())
    office_to_cluster = {off: 1 for off in sorted_offices}

# ── 3. Export CSVs & Plot Raw ─────────────────────────────────────────────────
print("\n3. Generating CSV tables & visualisations for each day...")

all_days = set()
for s in co2_data.values():
    all_days.update(s.index.normalize().unique())

for day_start in sorted(all_days):
    date_str = day_start.strftime("%Y-%m-%d")
    day_end = day_start + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
    
    raw_list = []
    for off in sorted_offices:
        s = co2_data[off].loc[day_start:day_end]
        if not s.empty:
            raw_list.append(s.rename(off))
            
    if not raw_list:
        continue
        
    # Build Raw DataFrame (sparse, timestamps preserved)
    df_raw = pd.concat(raw_list, axis=1)
    
    # Derivations
    df_10m = df_raw.resample("10min").mean()
    df_1h = df_raw.resample("1H").mean()
    
    # Export CSVs
    df_raw.to_csv(os.path.join(OUTPUT_DIR, "raw", f"co2_raw_{date_str}.csv"))
    df_10m.to_csv(os.path.join(OUTPUT_DIR, "10min", f"co2_10min_{date_str}.csv"))
    df_1h.to_csv(os.path.join(OUTPUT_DIR, "hourly", f"co2_hourly_{date_str}.csv"))
    
    # ── VISUALIZE RAW TABLE ──
    fig, ax = plt.subplots(figsize=(16, 9))
    fig.patch.set_facecolor("#0a0a0f")
    ax.set_facecolor("#12121f")
    
    # Using the modern colormaps API to avoid all deprecation warnings
    cluster_cmap = matplotlib.colormaps["tab10"].resampled(len(set(office_to_cluster.values())) + 1)
    
    # Track which clusters we've added to the legend so we don't have 51 entries
    added_to_legend = set()

    for off in sorted_offices:
        if off not in df_raw.columns: continue
        
        s_plot = df_raw[off].dropna()
        if s_plot.empty: continue
        
        cid = office_to_cluster.get(off, 1)
        cluster_color = cluster_cmap(cid % 10)
        
        # Label only if it's the first member of the cluster (to keep legend clean) or all if desired
        # Here we label each line but prefix with cluster
        label_str = f"[{cid}] {off}"
        ax.plot(s_plot.index, s_plot.values, marker=".", markersize=2.5, 
                linewidth=0.8, alpha=0.7, color=cluster_color, label=label_str)
                    
    # Shaded Business Hours (8:00 - 18:00)
    ax.axvspan(day_start + pd.Timedelta(hours=8),
               day_start + pd.Timedelta(hours=18),
               color="#1a2a44", alpha=0.4, zorder=0)
    
    # Annotation for Business Hours
    ax.text(day_start + pd.Timedelta(hours=13), ax.get_ylim()[1] * 0.95, 
            "BUSINESS HOURS (8:00 - 18:00)", 
            color="#4a6a94", fontsize=10, fontweight='bold', ha='center', alpha=0.8)

    # Global Cluster Summary Annotation
    cluster_counts = pd.Series([office_to_cluster[off] for off in df_raw.columns]).value_counts().sort_index()
    summary_text = "Detected Behavioral Groups:\n" + "\n".join([f" Group {cid}: {count} offices" for cid, count in cluster_counts.items()])
    ax.text(0.02, 0.98, summary_text, transform=ax.transAxes, 
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='#1a1a2e', alpha=0.8, edgecolor='#444'),
            color='white', fontsize=9)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    
    ax.set_title(f"Weekly Behavioral Correlation - {date_str}", color="white", fontsize=16, pad=20)
    ax.set_xlabel("Time of Day", color="#888", fontsize=12)
    ax.set_ylabel("CO2 Concentration (ppm)", color="#888", fontsize=12)
    ax.tick_params(colors="#777", labelsize=10)
    ax.grid(True, color="#222", linewidth=0.5, linestyle='--')
    for s in ax.spines.values(): s.set_edgecolor("#333")
    
    # Legend update: group by cluster if possible, here we just shrink it
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), facecolor="#0a0a0f", 
              edgecolor="#444", labelcolor="white", fontsize=8, ncol=3 if len(df_raw.columns) > 20 else 1)
    
    # Footer
    plt.figtext(0.5, 0.01, f"Note: Lines are colored by Global Weekly Similarity (Behavioral Clusters).", 
                 ha="center", fontsize=9, color="#555", fontstyle='italic')

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "raw", f"co2_raw_plot_{date_str}.png"), dpi=140, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    
    print(f"  [EXPORTED] {date_str} -> raw.csv, 10min.csv, hourly.csv + raw_plot.png")

print(f"\n✅ All complete! Check {OUTPUT_DIR}/")
