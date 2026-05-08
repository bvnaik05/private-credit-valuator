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

hl-credit-risk/
├── data/ ← raw data (not committed, see .gitignore)
├── notebooks/
│ ├── 01_eda.ipynb ← exploratory analysis
│ ├── 02_feature_engineering.ipynb
│ ├── 03_model_training.ipynb
│ └── 04_fair_value.ipynb
├── src/
│ ├── snowflake_connect.py ← Snowflake connector
│ ├── features.py ← feature engineering functions
│ ├── model.py ← training pipeline
│ └── valuation.py ← DCF and stress test logic
├── snowflake/
│ └── schema.sql ← table definitions
├── outputs/ ← model results, Excel exports
└── requirements.txt

---

## Key results

_(To be updated as project progresses)_

- Model AUC: TBD
- Portfolio default rate: TBD
- Stress test NAV impact: TBD

---

## Domain context

This project is built around concepts central to private credit
valuation:

- **PD (Probability of Default)** — likelihood a borrower stops paying
- **LGD (Loss Given Default)** — % of loan lost if default occurs
- **DCF (Discounted Cash Flow)** — present value of future loan payments
- **ASC 820** — US accounting standard requiring fair value reporting
  for fund portfolios (what HL's clients must comply with every quarter)

---

## Author

BHARGAVI NAIK | [https://www.linkedin.com/in/naikbhargavi05/]
