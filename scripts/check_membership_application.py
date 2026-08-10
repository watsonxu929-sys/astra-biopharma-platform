import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = "sqlite:///data/rehearsal/v06j_app_migrated.db"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("PRAGMA table_info(v04f_club_applications)"))
    columns = result.fetchall()
    print("Table columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    result = conn.execute(text("SELECT * FROM v04f_club_applications ORDER BY id DESC LIMIT 3"))
    rows = result.mappings().all()
    print(f"\nLatest 3 applications:")
    for row in rows:
        print(f"\nRow: {dict(row)}")