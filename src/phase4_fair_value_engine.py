import pandas as pd
import numpy as np
import pickle
from datetime import datetime
import os
from pathlib import Path
from snowflake_connect import get_connection

def load_phase3_outputs():
    """Load predictions and model from Phase 3"""
    
    print("\n[STEP 1] Loading Phase 3 Model Outputs...")
    
    # Find the latest test predictions file
    pred_files = list(Path('data/processed').glob('test_predictions_*.csv'))
    if not pred_files:
        raise FileNotFoundError("No test_predictions file found. Run Phase 3 first.")
    
    latest_pred_file = sorted(pred_files)[-1]
    predictions = pd.read_csv(latest_pred_file)
    
    # Find the latest model file
    model_files = list(Path('models').glob('xgboost_pd_model_*.pkl'))
    if not model_files:
        raise FileNotFoundError("No model file found. Run Phase 3 first.")
    
    latest_model_file = sorted(model_files)[-1]
    with open(latest_model_file, 'rb') as f:
        model = pickle.load(f)
    
    print(f"   ✓ Loaded predictions: {latest_pred_file.name}")
    print(f"   ✓ Loaded model: {latest_model_file.name}")
    print(f"   ✓ Predictions shape: {predictions.shape}")
    
    return predictions, model

def load_original_data():
    """Load the original loan data from Snowflake"""
    
    print("\n[STEP 2] Loading Original Loan Features from Snowflake...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("USE DATABASE HL_CREDIT_RISK")
    cursor.execute("USE SCHEMA PUBLIC")
    
    # Load all data
    cursor.execute("""
        SELECT 
            loan_amnt, funded_amnt, term, int_rate, grade, sub_grade,
            annual_inc, dti, delinq_2yrs, fico_range_low, fico_range_high,
            open_acc, pub_rec, revol_util, total_acc, loan_status,
            purpose, home_ownership, addr_state, issue_d, target
        FROM LOANS_RAW
    """)
    
    all_data = cursor.fetchall()
    df = pd.DataFrame(all_data, columns=[
        'loan_amnt', 'funded_amnt', 'term', 'int_rate', 'grade', 'sub_grade',
        'annual_inc', 'dti', 'delinq_2yrs', 'fico_range_low', 'fico_range_high',
        'open_acc', 'pub_rec', 'revol_util', 'total_acc', 'loan_status',
        'purpose', 'home_ownership', 'addr_state', 'issue_d', 'target'
    ])
    
    conn.close()
    
    # Compute missing engineered features
    df['fico_mid'] = (df['fico_range_low'] + df['fico_range_high']) / 2
    df['fico_range_width'] = df['fico_range_high'] - df['fico_range_low']
    
    print(f"   ✓ Loaded {len(df):,} loans from Snowflake")
    print(f"   ✓ Features available: {len(df.columns)}")
    
    return df

def calculate_lgd(grade, home_ownership, dti):
    """Calculate Loss Given Default based on loan characteristics"""
    
    # Base LGD by grade
    grade_lgd = {
        'A': 0.25, 'B': 0.35, 'C': 0.45, 'D': 0.55,
        'E': 0.65, 'F': 0.75, 'G': 0.85
    }
    
    # Adjust for home ownership
    home_adjustment = {
        'MORTGAGE': -0.05, 'OWN': 0.00, 'RENT': 0.10
    }
    
    # Adjust for DTI
    if dti > 40:
        dti_adjustment = 0.15
    elif dti > 30:
        dti_adjustment = 0.10
    elif dti > 20:
        dti_adjustment = 0.05
    else:
        dti_adjustment = 0.00
    
    base_lgd = grade_lgd.get(grade, 0.50)
    adjusted_lgd = base_lgd + home_adjustment.get(home_ownership, 0) + dti_adjustment
    
    return np.clip(adjusted_lgd, 0.10, 0.95)

def calculate_expected_loss(pd_prob, lgd, loan_amount):
    """Calculate Expected Loss"""
    return pd_prob * lgd * loan_amount

def simple_fair_value(loan_amnt, int_rate, pd_prob, lgd, term_months):
    """
    Simplified Fair Value = Par Value × (1 - PD × LGD) + Interest Premium
    
    This model avoids DCF complexity and prevents NaN/complex numbers
    """
    # Cap values to reasonable ranges
    pd_prob = np.clip(pd_prob, 0.0, 0.99)
    lgd = np.clip(lgd, 0.0, 0.95)
    
    # Expected recovery
    expected_loss_pct = pd_prob * lgd
    recovery_pct = 1.0 - expected_loss_pct
    recovery_value = loan_amnt * recovery_pct
    
    # Interest premium (assume 36-month average holding period for illiquid loan)
    expected_holding_months = min(term_months, 36)
    monthly_interest_rate = int_rate / 100 / 12
    interest_premium = loan_amnt * (monthly_interest_rate * expected_holding_months)
    
    # Fair value
    fair_value = recovery_value + interest_premium
    
    return max(fair_value, loan_amnt * 0.3)  # Floor at 30% of par

def build_portfolio_analytics():
    """Build portfolio analytics dataset"""
    
    print("\n" + "="*70)
    print("PHASE 4: FAIR VALUE ENGINE & STRESS TESTING")
    print("="*70)
    
    # Load data
    predictions, model = load_phase3_outputs()
    df_loans = load_original_data()
    
    # Use only test set loans (last 40,000 rows)
    print("\n[STEP 3] Merging Data & Calculating Analytics...")
    
    df_portfolio = df_loans.iloc[-len(predictions):].copy().reset_index(drop=True)
    df_portfolio['pd_prob'] = predictions['pred_default_prob'].values
    df_portfolio['actual_default'] = predictions['actual'].values
    
    # Calculate LGD
    df_portfolio['lgd'] = df_portfolio.apply(
        lambda row: calculate_lgd(row['grade'], row['home_ownership'], row['dti']),
        axis=1
    )
    
    print(f"   ✓ LGD calculated for {len(df_portfolio):,} loans")
    print(f"   ✓ Avg LGD: {df_portfolio['lgd'].mean():.2%}")
    
    # Calculate Expected Loss
    df_portfolio['expected_loss'] = df_portfolio.apply(
        lambda row: calculate_expected_loss(row['pd_prob'], row['lgd'], row['loan_amnt']),
        axis=1
    )
    
    print(f"   ✓ Expected Loss calculated")
    print(f"   ✓ Total Expected Loss: ${df_portfolio['expected_loss'].sum():,.0f}")
    
    # Convert term to months
    df_portfolio['term_months'] = df_portfolio['term'].str.extract(r'(\d+)').astype(int)
    
    # Calculate Fair Value
    print("\n[STEP 4] Calculating Fair Value...")
    
    df_portfolio['fair_value'] = df_portfolio.apply(
        lambda row: simple_fair_value(row['loan_amnt'], row['int_rate'], row['pd_prob'], row['lgd'], row['term_months']),
        axis=1
    )
    
    print(f"   ✓ Fair Value calculated for {len(df_portfolio):,} loans")
    print(f"   ✓ Total Fair Value: ${df_portfolio['fair_value'].sum():,.0f}")
    print(f"   ✓ Total Loan Amount: ${df_portfolio['loan_amnt'].sum():,.0f}")
    
    # Mark-to-Market
    df_portfolio['fair_value_pct'] = (df_portfolio['fair_value'] / df_portfolio['loan_amnt'] * 100).round(2)
    df_portfolio['mtm_gain_loss'] = df_portfolio['fair_value'] - df_portfolio['loan_amnt']
    
    print(f"   ✓ Mark-to-Market: ${df_portfolio['mtm_gain_loss'].sum():,.0f}")
    
    return df_portfolio

def apply_stress_scenarios(df_portfolio):
    """Apply stress testing scenarios"""
    
    print("\n[STEP 5] Running Stress Testing Scenarios...")
    
    stress_results = {}
    
    # BASE CASE
    stress_results['Base Case'] = {
        'total_fv': df_portfolio['fair_value'].sum(),
        'total_par': df_portfolio['loan_amnt'].sum(),
        'total_el': df_portfolio['expected_loss'].sum(),
        'avg_pd': df_portfolio['pd_prob'].mean(),
        'mtm': df_portfolio['mtm_gain_loss'].sum()
    }
    
    print("   Scenario 1: BASE CASE (Current Market)")
    print(f"      Fair Value: ${stress_results['Base Case']['total_fv']:,.0f}")
    print(f"      Total EL: ${stress_results['Base Case']['total_el']:,.0f}")
    
    # MILD RECESSION
    df_stress_mild = df_portfolio.copy()
    df_stress_mild['pd_prob_stressed'] = np.clip(df_portfolio['pd_prob'] * 1.3, 0.0, 0.99)
    df_stress_mild['lgd_stressed'] = np.clip(df_portfolio['lgd'] * 1.1, 0.0, 0.95)
    
    df_stress_mild['expected_loss_stressed'] = df_stress_mild.apply(
        lambda row: calculate_expected_loss(row['pd_prob_stressed'], row['lgd_stressed'], row['loan_amnt']),
        axis=1
    )
    
    df_stress_mild['fair_value_stressed'] = df_stress_mild.apply(
        lambda row: simple_fair_value(row['loan_amnt'], row['int_rate'] * 1.1, 
                                      row['pd_prob_stressed'], row['lgd_stressed'], row['term_months']),
        axis=1
    )
    
    stress_results['Mild Recession'] = {
        'total_fv': df_stress_mild['fair_value_stressed'].sum(),
        'total_par': df_stress_mild['loan_amnt'].sum(),
        'total_el': df_stress_mild['expected_loss_stressed'].sum(),
        'avg_pd': df_stress_mild['pd_prob_stressed'].mean(),
        'mtm': df_stress_mild['fair_value_stressed'].sum() - df_stress_mild['loan_amnt'].sum()
    }
    
    print("\n   Scenario 2: MILD RECESSION")
    print(f"      PD multiplier: 1.3x | LGD increase: +10% | Rate increase: +10%")
    print(f"      Fair Value: ${stress_results['Mild Recession']['total_fv']:,.0f}")
    print(f"      Total EL: ${stress_results['Mild Recession']['total_el']:,.0f}")
    print(f"      Impact: ${stress_results['Mild Recession']['total_fv'] - stress_results['Base Case']['total_fv']:,.0f}")
    
    # SEVERE RECESSION
    df_stress_severe = df_portfolio.copy()
    df_stress_severe['pd_prob_stressed'] = np.clip(df_portfolio['pd_prob'] * 1.8, 0.0, 0.99)
    df_stress_severe['lgd_stressed'] = np.clip(df_portfolio['lgd'] * 1.25, 0.0, 0.95)
    
    df_stress_severe['expected_loss_stressed'] = df_stress_severe.apply(
        lambda row: calculate_expected_loss(row['pd_prob_stressed'], row['lgd_stressed'], row['loan_amnt']),
        axis=1
    )
    
    df_stress_severe['fair_value_stressed'] = df_stress_severe.apply(
        lambda row: simple_fair_value(row['loan_amnt'], row['int_rate'] * 1.25, 
                                      row['pd_prob_stressed'], row['lgd_stressed'], row['term_months']),
        axis=1
    )
    
    stress_results['Severe Recession'] = {
        'total_fv': df_stress_severe['fair_value_stressed'].sum(),
        'total_par': df_stress_severe['loan_amnt'].sum(),
        'total_el': df_stress_severe['expected_loss_stressed'].sum(),
        'avg_pd': df_stress_severe['pd_prob_stressed'].mean(),
        'mtm': df_stress_severe['fair_value_stressed'].sum() - df_stress_severe['loan_amnt'].sum()
    }
    
    print("\n   Scenario 3: SEVERE RECESSION")
    print(f"      PD multiplier: 1.8x | LGD increase: +25% | Rate increase: +25%")
    print(f"      Fair Value: ${stress_results['Severe Recession']['total_fv']:,.0f}")
    print(f"      Total EL: ${stress_results['Severe Recession']['total_el']:,.0f}")
    print(f"      Impact: ${stress_results['Severe Recession']['total_fv'] - stress_results['Base Case']['total_fv']:,.0f}")
    
    return df_portfolio, df_stress_mild, df_stress_severe, stress_results

def create_powerbi_datasets(df_portfolio, df_stress_mild, df_stress_severe, stress_results):
    """Create clean datasets for Power BI"""
    
    print("\n[STEP 6] Creating Power BI Datasets...")
    
    os.makedirs('data/powerbi', exist_ok=True)
    
    # DATASET 1: LOAN-LEVEL PORTFOLIO
    powerbi_loans = df_portfolio[[
        'loan_amnt', 'int_rate', 'grade', 'dti', 'annual_inc',
        'fico_mid', 'home_ownership', 'purpose', 'addr_state',
        'pd_prob', 'lgd', 'expected_loss', 'fair_value', 'fair_value_pct',
        'mtm_gain_loss', 'actual_default', 'term_months'
    ]].copy()
    
    powerbi_loans.to_csv('data/powerbi/loan_portfolio.csv', index=False)
    print(f"   ✓ loan_portfolio.csv ({len(powerbi_loans):,} loans)")
    
    # DATASET 2: PORTFOLIO SUMMARY BY GRADE
    grade_summary = df_portfolio.groupby('grade').agg({
        'loan_amnt': ['sum', 'count', 'mean'],
        'int_rate': 'mean',
        'pd_prob': 'mean',
        'lgd': 'mean',
        'expected_loss': 'sum',
        'fair_value': 'sum',
        'actual_default': 'sum'
    }).round(2)
    
    grade_summary.columns = ['Total_Par', 'Loan_Count', 'Avg_Loan_Amount',
                             'Avg_Int_Rate', 'Avg_PD', 'Avg_LGD',
                             'Total_EL', 'Total_FV', 'Actual_Defaults']
    
    grade_summary['Default_Rate_Actual'] = (grade_summary['Actual_Defaults'] / grade_summary['Loan_Count'] * 100).round(2)
    grade_summary['FV_Pct'] = (grade_summary['Total_FV'] / grade_summary['Total_Par'] * 100).round(2)
    grade_summary['MTM'] = grade_summary['Total_FV'] - grade_summary['Total_Par']
    
    grade_summary.to_csv('data/powerbi/portfolio_by_grade.csv')
    print(f"   ✓ portfolio_by_grade.csv (7 grades)")
    
    # DATASET 3: STRESS TEST SCENARIOS
    stress_df = pd.DataFrame(stress_results).T
    stress_df['nav_impact'] = stress_df['total_fv'] - stress_results['Base Case']['total_fv']
    stress_df['nav_impact_pct'] = (stress_df['nav_impact'] / stress_results['Base Case']['total_fv'] * 100).round(2)
    stress_df = stress_df.round(0)
    
    stress_df.to_csv('data/powerbi/stress_scenarios.csv')
    print(f"   ✓ stress_scenarios.csv (3 scenarios)")
    
    # DATASET 4: PORTFOLIO SUMMARY (Dashboard KPIs)
    portfolio_kpis = pd.DataFrame({
        'Metric': [
            'Total Par', 'Total Fair Value', 'Total Expected Loss',
            'Mark-to-Market', 'Portfolio Avg PD', 'Portfolio Avg LGD',
            'Default Rate (Actual)', 'FV as % of Par',
            'High Risk (Grade F-G) Count', 'High Risk Par'
        ],
        'Value': [
            df_portfolio['loan_amnt'].sum(),
            df_portfolio['fair_value'].sum(),
            df_portfolio['expected_loss'].sum(),
            df_portfolio['mtm_gain_loss'].sum(),
            df_portfolio['pd_prob'].mean(),
            df_portfolio['lgd'].mean(),
            df_portfolio['actual_default'].mean(),
            (df_portfolio['fair_value'].sum() / df_portfolio['loan_amnt'].sum() * 100),
            len(df_portfolio[df_portfolio['grade'].isin(['F', 'G'])]),
            df_portfolio[df_portfolio['grade'].isin(['F', 'G'])]['loan_amnt'].sum()
        ]
    })
    
    portfolio_kpis.to_csv('data/powerbi/portfolio_kpis.csv', index=False)
    print(f"   ✓ portfolio_kpis.csv (10 KPIs)")
    
    # DATASET 5: GEOGRAPHIC DISTRIBUTION
    state_summary = df_portfolio.groupby('addr_state').agg({
        'loan_amnt': ['sum', 'count'],
        'pd_prob': 'mean',
        'fair_value': 'sum',
        'expected_loss': 'sum',
        'actual_default': 'sum'
    }).round(2)
    
    state_summary.columns = ['Total_Par', 'Loan_Count', 'Avg_PD', 'Total_FV', 'Total_EL', 'Actual_Defaults']
    state_summary['Default_Rate'] = (state_summary['Actual_Defaults'] / state_summary['Loan_Count'] * 100).round(2)
    
    state_summary.to_csv('data/powerbi/portfolio_by_state.csv')
    print(f"   ✓ portfolio_by_state.csv ({len(state_summary)} states)")
    
    # DATASET 6: RISK MATRIX
    risk_matrix = pd.crosstab(
        df_portfolio['grade'],
        pd.cut(df_portfolio['pd_prob'], bins=[0, 0.1, 0.2, 0.3, 0.5, 1.0], 
               labels=['Very Low', 'Low', 'Medium', 'High', 'Very High']),
        values=df_portfolio['loan_amnt'],
        aggfunc='sum'
    ).fillna(0)
    
    risk_matrix.to_csv('data/powerbi/risk_matrix.csv')
    print(f"   ✓ risk_matrix.csv (7 grades × 5 PD buckets)")
    
    print("\n   All datasets created successfully!")
    
    return powerbi_loans, grade_summary, stress_df

def main():
    """Main Phase 4 execution"""
    
    try:
        # Build portfolio analytics
        df_portfolio = build_portfolio_analytics()
        
        # Apply stress scenarios
        df_portfolio, df_stress_mild, df_stress_severe, stress_results = apply_stress_scenarios(df_portfolio)
        
        # Create Power BI datasets
        powerbi_loans, grade_summary, stress_df = create_powerbi_datasets(
            df_portfolio, df_stress_mild, df_stress_severe, stress_results
        )
        
        # FINAL SUMMARY
        print("\n" + "="*70)
        print("PHASE 4 SUMMARY")
        print("="*70)
        
        print("\n📊 PORTFOLIO METRICS:")
        print(f"   Total Loans: {len(df_portfolio):,}")
        print(f"   Total Par (Par Value): ${df_portfolio['loan_amnt'].sum():,.0f}")
        print(f"   Total Fair Value: ${df_portfolio['fair_value'].sum():,.0f}")
        print(f"   Mark-to-Market: ${df_portfolio['mtm_gain_loss'].sum():,.0f}")
        print(f"   FV as % of Par: {(df_portfolio['fair_value'].sum() / df_portfolio['loan_amnt'].sum() * 100):.2f}%")
        print(f"\n   Total Expected Loss: ${df_portfolio['expected_loss'].sum():,.0f}")
        print(f"   Portfolio Avg PD: {df_portfolio['pd_prob'].mean():.2%}")
        print(f"   Portfolio Avg LGD: {df_portfolio['lgd'].mean():.2%}")
        
        print("\n💾 POWER BI DATASETS CREATED:")
        print("   ✓ data/powerbi/loan_portfolio.csv - Full loan-level data")
        print("   ✓ data/powerbi/portfolio_by_grade.csv - Summary by loan grade")
        print("   ✓ data/powerbi/stress_scenarios.csv - Stress test results")
        print("   ✓ data/powerbi/portfolio_kpis.csv - Dashboard KPIs")
        print("   ✓ data/powerbi/portfolio_by_state.csv - Geographic analysis")
        print("   ✓ data/powerbi/risk_matrix.csv - Risk heatmap data")
        
        print("\n" + "="*70)
        print("✅ PHASE 4 COMPLETE: FAIR VALUE ENGINE & STRESS TESTING")
        print("="*70)
        print("\nNext Step: Import these CSV files into Power BI")
        print("Files Location: data/powerbi/")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
