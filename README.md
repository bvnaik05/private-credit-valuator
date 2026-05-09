# Private Credit Risk & Fair Value Estimator

### Built to mirror Portfolio Valuation workflows at alternative asset managers

---

## What this project does

This project automates two tasks that Portfolio Valuation teams like
Houlihan Lokey's FVA division perform every quarter:

1. **Default Risk Scoring** — predicts the probability of default (PD)
   for each loan in a portfolio using XGBoost, trained on 200,000+
   real loan records from Lending Club (2007–2018)

2. **Fair Value Estimation** — uses the PD score + live market interest
   rates (via FRED API) to compute the fair value of each loan using a
   DCF model, exactly as required under ASC 820 fair value reporting
   standards

3. **Stress Testing** — simulates a recession scenario (income –25%,
   rates +200bps) and shows the impact on portfolio NAV

---

## Tech stack

| Layer          | Tools                                   |
| -------------- | --------------------------------------- |
| Data warehouse | Snowflake                               |
| Modeling       | Python, XGBoost, SHAP                   |
| Market data    | FRED API, yfinance                      |
| Visualization  | Power BI                                |
| Workflow       | Jupyter Notebooks, pandas, scikit-learn |

---

## Project structure

private-credit-valuator/
├── data/                          ← raw data (not committed)
├── notebooks/
│   └── 01_eda.ipynb               ← exploratory data analysis
├── src/
│   ├── snowflake_connect.py       ← Snowflake connection manager
│   ├── load_to_snowflake.py       ← data ingestion pipeline
│   ├── setup_schema.py            ← database schema setup
│   ├── phase1_report.py           ← data validation & EDA report
│   ├── phase2_feature_engineering.py  ← feature engineering & ML prep
│   ├── phase3_xgboost_model.py    ← XGBoost PD model training
│   └── phase4_fair_value_engine.py    ← DCF valuation & stress testing
├── snowflake/
│   └── schema.sql                 ← table definitions
├── outputs/
│   └── plots/                     ← ROC curve, SHAP, confusion matrix
├── powerbi/
│   └── Private_Credit_Valuation.pbix  ← Power BI dashboard
└── requirements.txt

---

## Key results

| Metric | Value |
|---|---|
| Dataset | 200,000 Lending Club loans (2007–2018) |
| Default Rate | 17.9% |
| Model AUC-ROC | 0.7055 ✓ |
| Model Recall | 67.53% (catches 2 in 3 defaults) |
| Portfolio Par Value | $602.68M |
| Portfolio Fair Value | $702.23M |
| Mark-to-Market Gain | +$99.55M (16.5% premium) |
| Total Expected Loss | $127.26M |
| Mild Recession NAV Impact | -$31.39M (-4.5%) |
| Severe Recession NAV Impact | -$78.58M (-11.2%) |
| Portfolio Avg PD | 45.22% |
| Portfolio Avg LGD | 46.28% |

![Dashboard Overview](outputs/powerbi_image.png)

---

## Domain context

This project is built around concepts central to private credit
valuation:

- **PD (Probability of Default)** — likelihood a borrower stops paying
- **LGD (Loss Given Default)** — % of loan lost if default occurs
- **DCF (Discounted Cash Flow)** — present value of future loan payments
- **ASC 820** — US accounting standard requiring fair value reporting
  for fund portfolios (what HL's clients must comply with every quarter)

> **Note on Portfolio Avg PD:** The 45% avg PD reflects the test set composition
> (2016–2018 vintage loans with elevated default rates post-peak cycle).
> A production implementation would sample across vintages for a representative portfolio.

---

## Author

BHARGAVI NAIK | [https://www.linkedin.com/in/naikbhargavi05/]
