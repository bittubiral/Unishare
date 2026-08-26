import sqlite3

conn = sqlite3.connect("platform.db")
c = conn.cursor()

# Add missing columns one by one
columns_to_add = [
    ("reputation_score", "INTEGER DEFAULT 100"),
    ("warning_points", "INTEGER DEFAULT 0"),
    ("suspended_until", "TEXT"),
    ("suspension_reason", "TEXT"),
]

for col_name, col_type in columns_to_add:
    try:
        c.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
        print(f"✅ Added column: {col_name}")
    except sqlite3.OperationalError as e:
        print(f"⚠️ Skipped {col_name}: {e}")

conn.commit()
conn.close()
print("Migration complete!")