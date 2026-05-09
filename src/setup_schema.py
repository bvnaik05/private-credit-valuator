"""
Execute Snowflake schema setup via Python connector
More reliable than Web UI for multi-statement scripts
"""

import snowflake.connector
import os
from dotenv import load_dotenv

load_dotenv()

def execute_schema():
    """Load and execute schema.sql file"""
    
    print("=" * 60)
    print("HL Credit Risk - Snowflake Schema Setup")
    print("=" * 60 + "\n")
    
    # Connect
    print("🔗 Connecting to Snowflake...")
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE')
    )
    print("✅ Connected!\n")
    
    cursor = conn.cursor()
    
    # Create database FIRST (explicit)
    print("[1] Executing: CREATE DATABASE IF NOT EXISTS HL_CREDIT_RISK...")
    try:
        cursor.execute("CREATE DATABASE IF NOT EXISTS HL_CREDIT_RISK")
        print("    ✅ Success\n")
    except Exception as e:
        print(f"    ⚠️  {e}\n")
    
    # Read schema file
    with open('snowflake/schema.sql', 'r') as f:
        schema_content = f.read()
    
    # Split by semicolon and execute each statement (skip CREATE DATABASE)
    statements = [s.strip() for s in schema_content.split(';') if s.strip() and 'CREATE DATABASE' not in s]
    
    print(f"📝 Found {len(statements)} additional SQL statements to execute\n")
    
    # Debug: print ALL statements (cleaned)
    print("ALL Statements found:")
    for idx, stmt in enumerate(statements, 1):
        # Remove comments
        lines = stmt.split('\n')
        cleaned = '\n'.join([line for line in lines if not line.strip().startswith('--')])
        cleaned = cleaned.strip()
        if cleaned:
            preview = cleaned[:50].replace('\n', ' ')
            print(f"  [{idx}] {preview}...")
    print()
    
    for i, statement in enumerate(statements, 2):
        # Strip whitespace and comments
        stmt = statement.strip()
        
        # Remove leading comments
        lines = stmt.split('\n')
        actual_statement = '\n'.join([line for line in lines if not line.strip().startswith('--')])
        actual_statement = actual_statement.strip()
        
        if not actual_statement:
            continue
        
        # Show first 80 chars
        stmt_preview = actual_statement[:80].replace('\n', ' ')
        
        try:
            print(f"[{i}] Executing: {stmt_preview}...")
            cursor.execute(actual_statement)
            print(f"    ✅ Success\n")
        except Exception as e:
            print(f"    ❌ ERROR: {str(e)[:100]}\n")
            print(f"       Statement: {actual_statement[:100]}\n")
    
    # Verify tables were created
    print("\n📊 Verification - Checking tables in HL_CREDIT_RISK.PUBLIC:\n")
    
    cursor.execute("USE DATABASE HL_CREDIT_RISK")
    cursor.execute("SHOW TABLES IN SCHEMA PUBLIC")
    
    tables = cursor.fetchall()
    if tables:
        print(f"✅ Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[1]}")
    else:
        print("❌ No tables found!")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Schema setup complete!")

if __name__ == "__main__":
    execute_schema()
