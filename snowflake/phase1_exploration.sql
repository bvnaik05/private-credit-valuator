-- Phase 1: Data Setup & Exploration Queries
-- Run these in Snowflake to validate data and understand structure

USE DATABASE HL_CREDIT_RISK;
USE SCHEMA PUBLIC;
USE WAREHOUSE COMPUTE_WH;

-- 1. VERIFY DATA LOAD
SELECT COUNT(*) as total_rows FROM LOANS_RAW;

-- 2. DATA QUALITY CHECKS
SELECT 
    'loan_amnt' as field, COUNT(*) as total, COUNT(*) - COUNTIF(loan_amnt IS NULL) as non_null, 
    ROUND(100.0 * (COUNT(*) - COUNTIF(loan_amnt IS NULL)) / COUNT(*), 2) as pct_populated
FROM LOANS_RAW
UNION ALL
SELECT 
    'annual_inc', COUNT(*), COUNT(*) - COUNTIF(annual_inc IS NULL), 
    ROUND(100.0 * (COUNT(*) - COUNTIF(annual_inc IS NULL)) / COUNT(*), 2)
FROM LOANS_RAW
UNION ALL
SELECT 
    'int_rate', COUNT(*), COUNT(*) - COUNTIF(int_rate IS NULL), 
    ROUND(100.0 * (COUNT(*) - COUNTIF(int_rate IS NULL)) / COUNT(*), 2)
FROM LOANS_RAW
UNION ALL
SELECT 
    'dti', COUNT(*), COUNT(*) - COUNTIF(dti IS NULL), 
    ROUND(100.0 * (COUNT(*) - COUNTIF(dti IS NULL)) / COUNT(*), 2)
FROM LOANS_RAW
UNION ALL
SELECT 
    'fico_range_low', COUNT(*), COUNT(*) - COUNTIF(fico_range_low IS NULL), 
    ROUND(100.0 * (COUNT(*) - COUNTIF(fico_range_low IS NULL)) / COUNT(*), 2)
FROM LOANS_RAW;

-- 3. TARGET VARIABLE DISTRIBUTION
SELECT 
    target,
    CASE WHEN target = 1 THEN 'DEFAULT' ELSE 'NON-DEFAULT' END as status,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM LOANS_RAW), 2) as pct
FROM LOANS_RAW
GROUP BY target
ORDER BY target;

-- 4. LOAN GRADE DISTRIBUTION
SELECT 
    grade,
    COUNT(*) as count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM LOANS_RAW), 2) as pct,
    ROUND(AVG(int_rate), 2) as avg_int_rate,
    ROUND(AVG(loan_amnt), 0) as avg_loan_amnt
FROM LOANS_RAW
GROUP BY grade
ORDER BY grade;

-- 5. DEFAULT RATE BY GRADE
SELECT 
    grade,
    COUNT(*) as total_loans,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct
FROM LOANS_RAW
GROUP BY grade
ORDER BY default_rate_pct DESC;

-- 6. STATISTICAL SUMMARY
SELECT 
    'loan_amnt' as metric,
    ROUND(MIN(loan_amnt), 2) as min_val,
    ROUND(MAX(loan_amnt), 2) as max_val,
    ROUND(AVG(loan_amnt), 2) as mean_val,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY loan_amnt), 2) as median_val
FROM LOANS_RAW
UNION ALL
SELECT 
    'annual_inc',
    ROUND(MIN(annual_inc), 2),
    ROUND(MAX(annual_inc), 2),
    ROUND(AVG(annual_inc), 2),
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY annual_inc), 2)
FROM LOANS_RAW
UNION ALL
SELECT 
    'int_rate',
    ROUND(MIN(int_rate), 2),
    ROUND(MAX(int_rate), 2),
    ROUND(AVG(int_rate), 2),
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY int_rate), 2)
FROM LOANS_RAW
UNION ALL
SELECT 
    'dti',
    ROUND(MIN(dti), 2),
    ROUND(MAX(dti), 2),
    ROUND(AVG(dti), 2),
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY dti), 2)
FROM LOANS_RAW;

-- 7. HOME OWNERSHIP DISTRIBUTION
SELECT 
    home_ownership,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct
FROM LOANS_RAW
GROUP BY home_ownership
ORDER BY count DESC;

-- 8. PURPOSE DISTRIBUTION (top 10)
SELECT 
    purpose,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct
FROM LOANS_RAW
GROUP BY purpose
ORDER BY count DESC
LIMIT 10;

-- 9. TERM ANALYSIS
SELECT 
    term,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct,
    ROUND(AVG(int_rate), 2) as avg_int_rate
FROM LOANS_RAW
GROUP BY term
ORDER BY count DESC;

-- 10. FICO SCORE ANALYSIS
SELECT 
    CASE 
        WHEN fico_range_low < 620 THEN 'Poor (<620)'
        WHEN fico_range_low < 660 THEN 'Fair (620-659)'
        WHEN fico_range_low < 740 THEN 'Good (660-739)'
        WHEN fico_range_low < 800 THEN 'Very Good (740-799)'
        ELSE 'Excellent (800+)'
    END as fico_band,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct,
    ROUND(AVG(int_rate), 2) as avg_int_rate
FROM LOANS_RAW
GROUP BY fico_band
ORDER BY fico_range_low;

-- 11. TOP STATES BY LOAN VOLUME
SELECT 
    addr_state,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct
FROM LOANS_RAW
GROUP BY addr_state
ORDER BY count DESC
LIMIT 15;

-- 12. DELINQUENCY HISTORY ANALYSIS
SELECT 
    CASE 
        WHEN delinq_2yrs = 0 THEN 'No Delinquencies'
        WHEN delinq_2yrs BETWEEN 1 AND 2 THEN '1-2 Delinquencies'
        WHEN delinq_2yrs >= 3 THEN '3+ Delinquencies'
    END as delinq_band,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct
FROM LOANS_RAW
GROUP BY delinq_band
ORDER BY delinq_2yrs;

-- 13. DTI RATIO ANALYSIS (debt-to-income)
SELECT 
    CASE 
        WHEN dti < 10 THEN 'Low (<10%)'
        WHEN dti < 20 THEN 'Moderate (10-19%)'
        WHEN dti < 30 THEN 'High (20-29%)'
        ELSE 'Very High (30%+)'
    END as dti_band,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct,
    ROUND(AVG(int_rate), 2) as avg_int_rate
FROM LOANS_RAW
WHERE dti IS NOT NULL
GROUP BY dti_band
ORDER BY dti;

-- 14. LOAN AMOUNT BUCKET ANALYSIS
SELECT 
    CASE 
        WHEN loan_amnt < 5000 THEN '$0-5k'
        WHEN loan_amnt < 10000 THEN '$5k-10k'
        WHEN loan_amnt < 15000 THEN '$10k-15k'
        WHEN loan_amnt < 20000 THEN '$15k-20k'
        ELSE '$20k+'
    END as loan_amt_bucket,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct,
    ROUND(AVG(int_rate), 2) as avg_int_rate
FROM LOANS_RAW
GROUP BY loan_amt_bucket
ORDER BY loan_amnt;

-- 15. ISSUE DATE ANALYSIS (loan vintage)
SELECT 
    SUBSTR(issue_d, -4) as year_issued,
    COUNT(*) as count,
    COUNTIF(target = 1) as defaults,
    ROUND(100.0 * COUNTIF(target = 1) / COUNT(*), 2) as default_rate_pct
FROM LOANS_RAW
GROUP BY year_issued
ORDER BY year_issued DESC;
