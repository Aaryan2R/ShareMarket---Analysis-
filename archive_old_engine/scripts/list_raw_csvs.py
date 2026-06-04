# scripts/list_raw_csvs.py
from pathlib import Path
ROOT = Path("data/raw")
for d in sorted(ROOT.iterdir()):
    if not d.is_dir(): continue
    print("DIR:", d.name)
    for p in sorted(d.rglob("*.csv")):
        print("   ", p.relative_to(Path(".")))