from pathlib import Path
import sqlite3

root = Path.cwd()
db_files = [p for p in root.rglob("*.db") if p.is_file()]

print(f"Found DB files: {len(db_files)}")
for p in db_files:
    print(f"\n--- {p.relative_to(root)} ---")
    con = sqlite3.connect(str(p))
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()
        print("tables:", [r[0] for r in rows])
    finally:
        con.close()
