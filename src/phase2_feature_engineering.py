import pandas as pd
import numpy as np
from snowflake_connect import get_connection
from datetime import datetime
import os
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
import pickle

def create_feature_engineering_layer():
    """
    Phase 2: Feature Engineering & Data Preparation
    - Create derived financial metrics
    - Handle categorical encoding
    - Normalize and scale numerical features
    - Prepare train/test split
    """
    
    print("\n" + "="*70)
    print("PHASE 2: FEATURE ENGINEERING & ML DATA PREPARATION")
    print("="*70)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("USE DATABASE HL_CREDIT_RISK")
    cursor.execute("USE SCHEMA PUBLIC")
    
    # ==============================================================================
    # STEP 1: Load data from Snowflake
    # ==============================================================================
    print("\n[1/6] LOADING DATA FROM SNOWFLAKE...")
    
    cursor.execute("""
        SELECT 
            loan_amnt, funded_amnt, term, int_rate, grade, sub_grade,
            annual_inc, dti, delinq_2yrs, fico_range_low, fico_range_high,
            open_acc, pub_rec, revol_util, total_acc, loan_status,
            purpose, home_ownership, addr_state, issue_d, target
        FROM LOANS_RAW
    """)
    
    # Fetch all data
    all_data = cursor.fetchall()
    df = pd.DataFrame(all_data, columns=[
        'loan_amnt', 'funded_amnt', 'term', 'int_rate', 'grade', 'sub_grade',
        'annual_inc', 'dti', 'delinq_2yrs', 'fico_range_low', 'fico_range_high',
        'open_acc', 'pub_rec', 'revol_util', 'total_acc', 'loan_status',
        'purpose', 'home_ownership', 'addr_state', 'issue_d', 'target'
    ])
    
    print(f"   ✓ Loaded {len(df):,} records")
    
    # ==============================================================================
    # STEP 2: Feature Engineering
    # ==============================================================================
    print("\n[2/6] FEATURE ENGINEERING...")
    
    df_features = df.copy()
    
    # 2a. Credit Score Features
    df_features['fico_mid'] = (df_features['fico_range_low'] + df_features['fico_range_high']) / 2
    df_features['fico_range_width'] = df_features['fico_range_high'] - df_features['fico_range_low']
    
    # 2b. Loan-to-Income Ratios
    df_features['loan_to_income'] = df_features['loan_amnt'] / df_features['annual_inc']
    df_features['funded_to_income'] = df_features['funded_amnt'] / df_features['annual_inc']
    
    # 2c. Account Utilization
    df_features['acc_per_year'] = df_features['open_acc'] / (df_features['annual_inc'] / 10000).clip(lower=1)
    
    # 2d. Delinquency Indicator
    df_features['has_past_delinquency'] = (df_features['delinq_2yrs'] > 0).astype(int)
    
    # 2e. Term Binary (36 vs 60 months)
    df_features['term_60m'] = df_features['term'].str.contains('60').astype(int)
    
    # 2f. Interest Rate Categories
    df_features['high_int_rate'] = (df_features['int_rate'] > df_features['int_rate'].median()).astype(int)
    
    print("   Created features:")
    print("      • Credit score: fico_mid, fico_range_width")
    print("      • Leverage: loan_to_income, funded_to_income")
    print("      • Account metrics: acc_per_year")
    print("      • Delinquency: has_past_delinquency")
    print("      • Loan terms: term_60m, high_int_rate")
    
    # ==============================================================================
    # STEP 3: Categorical Encoding
    # ==============================================================================
    print("\n[3/6] CATEGORICAL ENCODING...")
    
    df_encoded = df_features.copy()
    
    # Label encode grade (ordinal: A < B < C < ... < G)
    grade_mapping = {'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7}
    df_encoded['grade_encoded'] = df_encoded['grade'].map(grade_mapping)
    
    # One-hot encode home_ownership
    home_ownership_dummies = pd.get_dummies(df_encoded['home_ownership'], prefix='home', drop_first=False)
    df_encoded = pd.concat([df_encoded, home_ownership_dummies], axis=1)
    
    # Verify home ownership columns were created
    home_cols = [col for col in df_encoded.columns if col.startswith('home_')]
    
    # Label encode top loan purposes
    top_purposes = df_encoded['purpose'].value_counts().head(8).index.tolist()
    df_encoded['purpose_encoded'] = df_encoded['purpose'].apply(
        lambda x: top_purposes.index(x) if x in top_purposes else -1
    )
    
    print("   Encoding applied:")
    print("      • Grade: ordinal encoding (A=1, ..., G=7)")
    print("      • Home ownership: one-hot encoding")
    print(f"      • Purpose: top 8 purposes + other (n={len(top_purposes)})")
    
    # ==============================================================================
    # STEP 4: Missing Value Imputation
    # ==============================================================================
    print("\n[4/6] MISSING VALUE HANDLING...")
    
    # Check for nulls
    null_counts = df_encoded.isnull().sum()
    if null_counts.sum() > 0:
        print("   Null values found:")
        for col, cnt in null_counts[null_counts > 0].items():
            print(f"      • {col}: {cnt:,}")
            # Impute numeric columns with median
            if df_encoded[col].dtype in ['float64', 'int64']:
                df_encoded[col] = df_encoded[col].fillna(df_encoded[col].median())
    else:
        print("   ✓ No null values detected")
    
    # ==============================================================================
    # STEP 5: Feature Selection for Model
    # ==============================================================================
    print("\n[5/6] FEATURE SELECTION FOR ML MODEL...")
    
    base_features = [
        'loan_amnt', 'int_rate', 'grade_encoded', 'dti', 'delinq_2yrs',
        'fico_mid', 'fico_range_width', 'open_acc', 'pub_rec', 'revol_util',
        'total_acc', 'loan_to_income', 'funded_to_income', 'has_past_delinquency',
        'term_60m', 'high_int_rate', 'purpose_encoded'
    ]
    
    # Add all home ownership columns
    feature_cols = base_features + home_cols
    
    # Verify all features exist
    available_features = [col for col in feature_cols if col in df_encoded.columns]
    missing_features = set(feature_cols) - set(available_features)
    
    if missing_features:
        print(f"   Warning: Missing features: {missing_features}")
    
    print(f"   ✓ Selected {len(available_features)} features for model")
    
    # ==============================================================================
    # STEP 6: Train/Test Split & Normalization
    # ==============================================================================
    print("\n[6/6] TRAIN/TEST SPLIT & NORMALIZATION...")
    
    X = df_encoded[available_features].copy()
    y = df_encoded['target'].copy()
    
    # Ensure all columns are numeric (drop any categorical)
    X = X.select_dtypes(include=[np.number])
    available_features = list(X.columns)
    
    # 80/20 split with stratification for class balance
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y  # Ensures same default rate in train/test
    )
    
    print(f"   Training set: {len(X_train):,} samples ({len(X_train)/len(X)*100:.1f}%)")
    print(f"      - Defaults: {y_train.sum():,} ({y_train.mean()*100:.2f}%)")
    print(f"   Test set: {len(X_test):,} samples ({len(X_test)/len(X)*100:.1f}%)")
    print(f"      - Defaults: {y_test.sum():,} ({y_test.mean()*100:.2f}%)")
    
    # Normalize numerical features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print("   ✓ Features normalized (StandardScaler)")
    
    # ==============================================================================
    # Save artifacts for Phase 3
    # ==============================================================================
    print("\n" + "="*70)
    print("SAVING ARTIFACTS FOR PHASE 3 (ML MODELING)...")
    print("="*70)
    
    os.makedirs('data/processed', exist_ok=True)
    
    # Save train/test data
    np.savez('data/processed/train_test_split.npz',
             X_train=X_train_scaled, X_test=X_test_scaled,
             y_train=y_train.values, y_test=y_test.values)
    
    # Save scaler
    with open('data/processed/scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save feature names
    with open('data/processed/feature_names.pkl', 'wb') as f:
        pickle.dump(available_features, f)
    
    # Save full processed dataframe for analysis
    df_encoded[available_features + ['target']].to_csv('data/processed/full_dataset_engineered.csv', index=False)
    
    print("   ✓ data/processed/train_test_split.npz (train/test data)")
    print("   ✓ data/processed/scaler.pkl (StandardScaler)")
    print("   ✓ data/processed/feature_names.pkl (feature list)")
    print("   ✓ data/processed/full_dataset_engineered.csv (full dataset)")
    
    # ==============================================================================
    # Summary Statistics
    # ==============================================================================
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)
    
    print("\nFeature Statistics (Training Set):")
    print(pd.DataFrame(X_train, columns=available_features).describe().T[['mean', 'std', 'min', 'max']])
    
    print("\n✅ PHASE 2 COMPLETE: DATA READY FOR ML MODELING")
    print("\nNext Steps (Phase 3):")
    print("  • Train XGBoost classifier for PD estimation")
    print("  • Evaluate model (AUC, Precision/Recall, SHAP)")
    print("  • Score all test samples and save PD predictions")
    print("="*70 + "\n")
    
    conn.close()
    
    return X_train_scaled, X_test_scaled, y_train.values, y_test.values, available_features

if __name__ == "__main__":
    create_feature_engineering_layer()
