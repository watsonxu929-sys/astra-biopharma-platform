import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text

DATABASE_URL = "sqlite:///data/rehearsal/v06j_app_migrated.db"
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
    tables = [row[0] for row in result]
    print(f"Tables ({len(tables)}):")
    for t in tables:
        print(f"  - {t}")
    
    result = conn.execute(text("SELECT COUNT(*) FROM organization"))
    org_count = result.scalar()
    print(f"\nOrganization count: {org_count}")
    
    if org_count > 0:
        result = conn.execute(text("SELECT id, name FROM organization LIMIT 5"))
        print("Sample organizations:")
        for row in result:
            print(f"  - id={row[0]}, name={row[1]}")