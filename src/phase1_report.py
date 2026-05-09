import pandas as pd
import numpy as np
from snowflake_connect import get_connection
from datetime import datetime
import os

def run_phase1_analysis():
    """Run comprehensive Phase 1 data validation and generate report"""
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Set context
    cursor.execute("USE DATABASE HL_CREDIT_RISK")
    cursor.execute("USE SCHEMA PUBLIC")
    
    print("\n" + "="*70)
    print("PHASE 1: DATA SETUP & EXPLORATION REPORT")
    print("="*70)
    
    # ==============================================================================
    # 1. VERIFY DATA LOAD
    # ==============================================================================
    print("\n[1/10] VERIFYING DATA LOAD...")
    cursor.execute("SELECT COUNT(*) as total_rows FROM LOANS_RAW")
    total_rows = cursor.fetchone()[0]
    print(f"   ✓ Total rows loaded: {total_rows:,}")
    
    # ==============================================================================
    # 2. DATA QUALITY CHECKS
    # ==============================================================================
    print("\n[2/10] DATA QUALITY CHECKS...")
    
    quality_query = """
    SELECT 
        'loan_amnt' as field, COUNT(CASE WHEN loan_amnt IS NOT NULL THEN 1 END) as non_null
    FROM LOANS_RAW
    UNION ALL
    SELECT 'annual_inc', COUNT(CASE WHEN annual_inc IS NOT NULL THEN 1 END) FROM LOANS_RAW
    UNION ALL
    SELECT 'int_rate', COUNT(CASE WHEN int_rate IS NOT NULL THEN 1 END) FROM LOANS_RAW
    UNION ALL
    SELECT 'dti', COUNT(CASE WHEN dti IS NOT NULL THEN 1 END) FROM LOANS_RAW
    UNION ALL
    SELECT 'fico_range_low', COUNT(CASE WHEN fico_range_low IS NOT NULL THEN 1 END) FROM LOANS_RAW
    """
    
    cursor.execute(quality_query)
    quality_data = cursor.fetchall()
    
    quality_df = pd.DataFrame(quality_data, columns=['field', 'non_null'])
    quality_df['pct_populated'] = (100.0 * quality_df['non_null'] / total_rows).round(2)
    
    for _, row in quality_df.iterrows():
        print(f"   {row['field']:<20}: {row['non_null']:>8,} rows ({row['pct_populated']:>5.1f}%)")
    
    # ==============================================================================
    # 3. TARGET VARIABLE DISTRIBUTION
    # ==============================================================================
    print("\n[3/10] TARGET VARIABLE (DEFAULT/NON-DEFAULT)...")
    
    target_query = """
    SELECT target, COUNT(*) as count
    FROM LOANS_RAW
    GROUP BY target
    ORDER BY target
    """
    
    cursor.execute(target_query)
    target_data = cursor.fetchall()
    target_df = pd.DataFrame(target_data, columns=['target', 'count'])
    target_df['status'] = target_df['target'].apply(lambda x: 'DEFAULT' if x == 1 else 'NON-DEFAULT')
    target_df['pct'] = (100.0 * target_df['count'] / total_rows).round(2)
    
    for _, row in target_df.iterrows():
        print(f"   {row['status']:<15}: {row['count']:>8,} ({row['pct']:>5.1f}%)")
    
    default_rate = (target_df[target_df['target'] == 1]['count'].values[0] / total_rows * 100)
    print(f"\n   📊 BASELINE DEFAULT RATE: {default_rate:.2f}%")
    
    # ==============================================================================
    # 4. LOAN GRADE DISTRIBUTION & DEFAULT RATES
    # ==============================================================================
    print("\n[4/10] DEFAULT RATE BY LOAN GRADE...")
    
    grade_query = """
    SELECT 
        grade,
        COUNT(*) as total_loans,
        COUNT(CASE WHEN target = 1 THEN 1 END) as defaults,
        ROUND(100.0 * COUNT(CASE WHEN target = 1 THEN 1 END) / COUNT(*), 2) as default_rate_pct
    FROM LOANS_RAW
    GROUP BY grade
    ORDER BY grade
    """
    
    cursor.execute(grade_query)
    grade_data = cursor.fetchall()
    grade_df = pd.DataFrame(grade_data, columns=['grade', 'total_loans', 'defaults', 'default_rate_pct'])
    
    for _, row in grade_df.iterrows():
        print(f"   Grade {row['grade']}: {row['total_loans']:>6,} loans | {row['defaults']:>6,} defaults | {row['default_rate_pct']:>5.1f}%")
    
    # ==============================================================================
    # 5. FINANCIAL METRICS SUMMARY
    # ==============================================================================
    print("\n[5/10] FINANCIAL METRICS SUMMARY...")
    
    stats_query = """
    SELECT 
        'loan_amnt' as metric,
        MIN(loan_amnt) as min_val, MAX(loan_amnt) as max_val,
        AVG(loan_amnt) as mean_val
    FROM LOANS_RAW
    UNION ALL
    SELECT 'annual_inc', MIN(annual_inc), MAX(annual_inc), AVG(annual_inc) FROM LOANS_RAW
    UNION ALL
    SELECT 'int_rate', MIN(int_rate), MAX(int_rate), AVG(int_rate) FROM LOANS_RAW
    UNION ALL
    SELECT 'dti', MIN(dti), MAX(dti), AVG(dti) FROM LOANS_RAW
    """
    
    cursor.execute(stats_query)
    stats_data = cursor.fetchall()
    stats_df = pd.DataFrame(stats_data, columns=['metric', 'min', 'max', 'mean'])
    
    for _, row in stats_df.iterrows():
        print(f"   {row['metric']:<15}: min=${row['min']:>10,.0f} | max=${row['max']:>10,.0f} | avg=${row['mean']:>10,.0f}")
    
    # ==============================================================================
    # 6. HOME OWNERSHIP ANALYSIS
    # ==============================================================================
    print("\n[6/10] HOME OWNERSHIP DISTRIBUTION...")
    
    home_query = """
    SELECT 
        home_ownership,
        COUNT(*) as count,
        COUNT(CASE WHEN target = 1 THEN 1 END) as defaults,
        ROUND(100.0 * COUNT(CASE WHEN target = 1 THEN 1 END) / COUNT(*), 2) as default_rate_pct
    FROM LOANS_RAW
    GROUP BY home_ownership
    ORDER BY count DESC
    """
    
    cursor.execute(home_query)
    home_data = cursor.fetchall()
    home_df = pd.DataFrame(home_data, columns=['home_ownership', 'count', 'defaults', 'default_rate_pct'])
    
    for _, row in home_df.iterrows():
        print(f"   {row['home_ownership']:<15}: {row['count']:>6,} | default_rate: {row['default_rate_pct']:>5.1f}%")
    
    # ==============================================================================
    # 7. FICO SCORE ANALYSIS
    # ==============================================================================
    print("\n[7/10] CREDIT SCORE (FICO) ANALYSIS...")
    
    fico_query = """
    SELECT 
        CASE 
            WHEN fico_range_low < 620 THEN 'Poor (< 620)'
            WHEN fico_range_low < 660 THEN 'Fair (620-659)'
            WHEN fico_range_low < 740 THEN 'Good (660-739)'
            WHEN fico_range_low < 800 THEN 'Very Good (740-799)'
            ELSE 'Excellent (800+)'
        END as fico_band,
        COUNT(*) as count,
        COUNT(CASE WHEN target = 1 THEN 1 END) as defaults,
        ROUND(100.0 * COUNT(CASE WHEN target = 1 THEN 1 END) / COUNT(*), 2) as default_rate_pct,
        ROUND(AVG(int_rate), 2) as avg_int_rate
    FROM LOANS_RAW
    GROUP BY fico_band
    ORDER BY CASE 
        WHEN fico_band LIKE 'Poor%' THEN 1
        WHEN fico_band LIKE 'Fair%' THEN 2
        WHEN fico_band LIKE 'Good%' THEN 3
        WHEN fico_band LIKE 'Very%' THEN 4
        ELSE 5
    END
    """
    
    cursor.execute(fico_query)
    fico_data = cursor.fetchall()
    fico_df = pd.DataFrame(fico_data, columns=['fico_band', 'count', 'defaults', 'default_rate_pct', 'avg_int_rate'])
    
    for _, row in fico_df.iterrows():
        print(f"   {row['fico_band']:<25}: {row['count']:>6,} | default_rate: {row['default_rate_pct']:>5.1f}% | avg_rate: {row['avg_int_rate']:.2f}%")
    
    # ==============================================================================
    # 8. DTI (DEBT-TO-INCOME) ANALYSIS
    # ==============================================================================
    print("\n[8/10] DTI RATIO (DEBT-TO-INCOME) ANALYSIS...")
    
    dti_query = """
    SELECT 
        CASE 
            WHEN dti < 10 THEN 'Low (< 10%)'
            WHEN dti < 20 THEN 'Moderate (10-19%)'
            WHEN dti < 30 THEN 'High (20-29%)'
            ELSE 'Very High (30%+)'
        END as dti_band,
        COUNT(*) as count,
        COUNT(CASE WHEN target = 1 THEN 1 END) as defaults,
        ROUND(100.0 * COUNT(CASE WHEN target = 1 THEN 1 END) / COUNT(*), 2) as default_rate_pct
    FROM LOANS_RAW
    WHERE dti IS NOT NULL
    GROUP BY dti_band
    ORDER BY CASE 
        WHEN dti_band LIKE 'Low%' THEN 1
        WHEN dti_band LIKE 'Moderate%' THEN 2
        WHEN dti_band LIKE 'High%' THEN 3
        ELSE 4
    END
    """
    
    cursor.execute(dti_query)
    dti_data = cursor.fetchall()
    dti_df = pd.DataFrame(dti_data, columns=['dti_band', 'count', 'defaults', 'default_rate_pct'])
    
    for _, row in dti_df.iterrows():
        print(f"   {row['dti_band']:<25}: {row['count']:>6,} | default_rate: {row['default_rate_pct']:>5.1f}%")
    
    # ==============================================================================
    # 9. TOP LOAN PURPOSES
    # ==============================================================================
    print("\n[9/10] TOP 5 LOAN PURPOSES...")
    
    purpose_query = """
    SELECT 
        purpose,
        COUNT(*) as count,
        COUNT(CASE WHEN target = 1 THEN 1 END) as defaults,
        ROUND(100.0 * COUNT(CASE WHEN target = 1 THEN 1 END) / COUNT(*), 2) as default_rate_pct
    FROM LOANS_RAW
    GROUP BY purpose
    ORDER BY count DESC
    LIMIT 5
    """
    
    cursor.execute(purpose_query)
    purpose_data = cursor.fetchall()
    purpose_df = pd.DataFrame(purpose_data, columns=['purpose', 'count', 'defaults', 'default_rate_pct'])
    
    for _, row in purpose_df.iterrows():
        print(f"   {row['purpose']:<25}: {row['count']:>6,} | default_rate: {row['default_rate_pct']:>5.1f}%")
    
    # ==============================================================================
    # 10. DATA SAMPLE
    # ==============================================================================
    print("\n[10/10] SAMPLE DATA (5 ROWS)...")
    
    sample_query = """
    SELECT 
        loan_amnt, annual_inc, int_rate, grade, target,
        dti, fico_range_low, home_ownership, purpose
    FROM LOANS_RAW
    LIMIT 5
    """
    
    cursor.execute(sample_query)
    sample_data = cursor.fetchall()
    sample_df = pd.DataFrame(sample_data, columns=['loan_amnt', 'annual_inc', 'int_rate', 'grade', 'target', 'dti', 'fico_range_low', 'home_ownership', 'purpose'])
    
    print("\n" + sample_df.to_string(index=False))
    
    # ==============================================================================
    # EXPORT REPORTS
    # ==============================================================================
    print("\n" + "="*70)
    print("GENERATING REPORTS...")
    print("="*70)
    
    # Create outputs directory if it doesn't exist
    os.makedirs('outputs', exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export to Excel
    excel_file = f'outputs/PHASE1_Data_Report_{timestamp}.xlsx'
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        target_df.to_excel(writer, sheet_name='Target Distribution', index=False)
        grade_df.to_excel(writer, sheet_name='Default by Grade', index=False)
        quality_df.to_excel(writer, sheet_name='Data Quality', index=False)
        home_df.to_excel(writer, sheet_name='Home Ownership', index=False)
        fico_df.to_excel(writer, sheet_name='FICO Analysis', index=False)
        dti_df.to_excel(writer, sheet_name='DTI Analysis', index=False)
        purpose_df.to_excel(writer, sheet_name='Loan Purpose', index=False)
        stats_df.to_excel(writer, sheet_name='Financial Metrics', index=False)
        sample_df.to_excel(writer, sheet_name='Sample Data', index=False)
    
    print(f"\n   ✓ Excel report saved: {excel_file}")
    
    # Export summary statistics to CSV
    csv_file = f'outputs/PHASE1_Summary_{timestamp}.csv'
    summary_data = {
        'Metric': [
            'Total Rows Loaded',
            'Default Rate (%)',
            'Avg Loan Amount ($)',
            'Avg Annual Income ($)',
            'Avg Interest Rate (%)',
            'Avg DTI (%)'
        ],
        'Value': [
            f"{total_rows:,}",
            f"{default_rate:.2f}",
            f"{stats_df[stats_df['metric']=='loan_amnt']['mean'].values[0]:,.0f}",
            f"{stats_df[stats_df['metric']=='annual_inc']['mean'].values[0]:,.0f}",
            f"{stats_df[stats_df['metric']=='int_rate']['mean'].values[0]:.2f}",
            f"{stats_df[stats_df['metric']=='dti']['mean'].values[0]:.2f}"
        ]
    }
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_csv(csv_file, index=False)
    print(f"   ✓ CSV summary saved: {csv_file}")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ PHASE 1 COMPLETE: DATA VALIDATED & READY FOR PHASE 2")
    print("="*70)
    print("\nNext Steps (Phase 2):")
    print("  • Feature engineering: create DTI, coverage ratios, delinquency flags")
    print("  • Exploratory visualizations: default rate by grade, FICO, loan amount")
    print("  • Prepare train/test split for ML model")
    print("="*70 + "\n")

if __name__ == "__main__":
    run_phase1_analysis()
