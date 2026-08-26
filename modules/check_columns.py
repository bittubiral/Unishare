import sqlite3

conn = sqlite3.connect("platform.db")
c = conn.cursor()

c.execute("PRAGMA table_info(users)")
columns = c.fetchall()

print("Current columns in 'users' table:")
for col in columns:
    print(f"  - {col[1]} ({col[2]})")

conn.close()