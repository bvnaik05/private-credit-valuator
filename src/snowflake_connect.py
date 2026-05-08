import snowflake.connector
import os
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

def get_connection():
    """Returns an active Snowflake connection using .env credentials"""
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        schema=os.getenv('SNOWFLAKE_SCHEMA')
    )
    return conn

def test_connection():
    """Quick test to verify Snowflake credentials work"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT_USER(), CURRENT_VERSION()")
        user, version = cursor.fetchone()
        print(f"✅ Connected to Snowflake!")
        print(f"   User: {user}")
        print(f"   Version: {version}")
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    test_connection()