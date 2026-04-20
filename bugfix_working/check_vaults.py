from pathlib import Path

root = Path(".")
models = {
    "Ideal":    root / "idealLoad_model",
    "NoIdeal":  root / "noIdealLoad_model",
    "Aswani":   root / "aswani_model",
}
all_ok = True
for name, mroot in models.items():
    runs_dir = mroot / "model" / "runs"
    runs = sorted(runs_dir.iterdir(), key=lambda d: d.stat().st_mtime, reverse=True) if runs_dir.exists() else []
    if runs:
        sql = runs[0] / "run" / "eplusout.sql"
        size_kb = round(sql.stat().st_size / 1024) if sql.exists() else 0
        status = "OK" if sql.exists() and size_kb > 50 else "MISSING or EMPTY"
        if status != "OK":
            all_ok = False
        print(f"  {name:10} | run: {runs[0].name} | SQL: {sql.exists()} ({size_kb} KB) | {status}")
    else:
        print(f"  {name:10} | NO RUNS FOUND")
        all_ok = False

print()
print("ALL VAULTS READY" if all_ok else "ONE OR MORE VAULTS MISSING — check above")
