import pandas as pd
import numpy as np
from snowflake_connect import get_connection
from dotenv import load_dotenv

load_dotenv()

def load_loans_to_snowflake(csv_path: str, sample_size: int = 200000):
    """
    Reads the Lending Club CSV, cleans it, applies target definition,
    and loads into Snowflake LOANS_RAW table.
    """
    print(f"📂 Reading data from {csv_path}...")
    
    key_columns = [
        'loan_amnt', 'funded_amnt', 'term', 'int_rate', 'grade',
        'sub_grade', 'annual_inc', 'dti', 'delinq_2yrs',
        'fico_range_low', 'fico_range_high', 'open_acc', 'pub_rec',
        'revol_util', 'total_acc', 'loan_status', 'purpose',
        'home_ownership', 'addr_state', 'issue_d'
    ]
    
    df = pd.read_csv(
        csv_path,
        compression='gzip',
        low_memory=False,
        usecols=key_columns,
        nrows=sample_size
    )
    
    print(f"   Loaded {len(df):,} rows from CSV")
    
    # Define target variable (1 = default, 0 = paid/current)
    default_statuses = [
        'Charged Off',
        'Default',
        'Late (31-120 days)',
        'Does not meet the credit policy. Status:Charged Off'
    ]
    
    df['target'] = df['loan_status'].apply(
        lambda x: 1 if x in default_statuses else 0
    )
    
    # Clean percentage fields (remove % sign)
    if df['int_rate'].dtype == object:
        df['int_rate'] = df['int_rate'].str.replace('%', '').astype(float)
    
    if df['revol_util'].dtype == object:
        df['revol_util'] = df['revol_util'].str.replace('%', '').astype(float)
    
    # Drop rows with nulls in critical columns
    df = df.dropna(subset=['annual_inc', 'dti', 'fico_range_low'])
    
    # Replace NaN with None (which maps to NULL in Snowflake)
    df = df.where(pd.notna(df), None)
    
    print(f"   After cleaning: {len(df):,} rows")
    print(f"   Default rate: {df['target'].mean():.1%}")
    print(f"   Defaults: {df['target'].sum():,}")
    print(f"   Non-defaults: {(df['target']==0).sum():,}")
    
    print("\n🔄 Connecting to Snowflake...")
    conn = get_connection()
    cursor = conn.cursor()
    
    # Explicitly set the database and schema context
    cursor.execute("USE DATABASE HL_CREDIT_RISK")
    cursor.execute("USE SCHEMA PUBLIC")
    
    # Clear any existing data
    print("   Clearing existing data from LOANS_RAW...")
    cursor.execute("TRUNCATE TABLE LOANS_RAW")
    
    print(f"\n📤 Uploading {len(df):,} rows to Snowflake...")
    
    # Reorder DataFrame columns to match table schema
    df = df[['loan_amnt', 'funded_amnt', 'term', 'int_rate', 'grade',
             'sub_grade', 'annual_inc', 'dti', 'delinq_2yrs',
             'fico_range_low', 'fico_range_high', 'open_acc', 'pub_rec',
             'revol_util', 'total_acc', 'loan_status', 'purpose',
             'home_ownership', 'addr_state', 'issue_d', 'target']]
    
    # Upload in batches
    batch_size = 10000
    total = len(df)
    
    for i in range(0, total, batch_size):
        batch = df.iloc[i:i+batch_size]
        
        # Build multi-row INSERT statement
        values_list = []
        for row in batch.values:
            # Convert values: None stays None, numbers as-is, strings quoted
            formatted_values = []
            for val in row:
                if val is None or (isinstance(val, float) and np.isnan(val)):
                    formatted_values.append("NULL")
                elif isinstance(val, str):
                    formatted_values.append(f"'{val.replace(chr(39), chr(39)+chr(39))}'")  # Escape single quotes
                else:
                    formatted_values.append(str(val))
            values_list.append(f"({','.join(formatted_values)})")
        
        sql = f"INSERT INTO LOANS_RAW VALUES {','.join(values_list)}"
        cursor.execute(sql)
        
        print(f"   ✓ Uploaded {min(i+batch_size, total):,}/{total:,} rows...")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Data loaded to Snowflake successfully!")
    print(f"\nTo verify in Snowflake, run:")
    print(f"   SELECT COUNT(*) FROM LOANS_RAW;")
    print(f"   SELECT * FROM LOANS_RAW LIMIT 10;")

if __name__ == "__main__":
    load_loans_to_snowflake(
        csv_path="data/accepted_2007_to_2018Q4.csv.gz",
        sample_size=200000
    )