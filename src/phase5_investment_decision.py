import pandas as pd
import numpy as np
import pickle
import requests
import os
from pathlib import Path
from datetime import datetime

# ==============================================================================
# CONFIGURATION
# ==============================================================================

from dotenv import load_dotenv
load_dotenv()
FRED_API_KEY = os.getenv('FRED_API_KEY', 'demo')

# Investment decision thresholds
THRESHOLDS = {
    'BUY':  {'max_pd': 0.20, 'min_ray': 4.0,  'max_lgd': 0.50},
    'HOLD': {'max_pd': 0.35, 'min_ray': 1.0,  'max_lgd': 0.65},
    # Anything outside HOLD thresholds = AVOID
}

# Stress scenario multipliers (mirrors Phase 4)
STRESS_MULTIPLIERS = {
    'Base Case':       {'pd': 1.00, 'lgd': 1.00, 'rate': 1.00},
    'Mild Recession':  {'pd': 1.30, 'lgd': 1.10, 'rate': 1.10},
    'Severe Recession':{'pd': 1.80, 'lgd': 1.25, 'rate': 1.25},
}


# ==============================================================================
# STEP 1 — FETCH LIVE MARKET DATA FROM FRED
# ==============================================================================

def fetch_fred_rate(series_id: str, api_key: str) -> float:
    """
    Fetch the latest value for a FRED data series.
    Falls back to a hardcoded default if the API call fails.
    """
    fallbacks = {
        'DGS10':  4.35,   # 10-year treasury yield (risk-free rate)
        'DGS2':   4.75,   # 2-year treasury yield
        'BAMLH0A0HYM2': 3.20,  # High-yield credit spread (OAS)
        'BAMLC0A0CM': 1.10,    # Investment grade credit spread
        'FEDFUNDS': 5.33,      # Fed funds rate
    }

    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}"
            f"&api_key={api_key}"
            f"&file_type=json"
            f"&limit=1"
            f"&sort_order=desc"
        )
        resp = requests.get(url, timeout=8)
        if resp.status_code == 200:
            obs = resp.json().get('observations', [])
            if obs:
                val = obs[0].get('value', '.')
                if val != '.':
                    return float(val)
    except Exception:
        pass

    print(f"   ⚠ FRED fallback used for {series_id}: {fallbacks.get(series_id, 0.0)}")
    return fallbacks.get(series_id, 0.0)


def get_market_context(api_key: str) -> dict:
    """
    Pull four key market rates from FRED.
    These are used as inputs to the fair value model and
    as the risk-free benchmark for investment decisions.
    """
    print("\n[STEP 1] Fetching live market data from FRED...")

    context = {
        'treasury_10y':     fetch_fred_rate('DGS10',         api_key),
        'treasury_2y':      fetch_fred_rate('DGS2',          api_key),
        'hy_spread':        fetch_fred_rate('BAMLH0A0HYM2',  api_key),
        'ig_spread':        fetch_fred_rate('BAMLC0A0CM',    api_key),
        'fed_funds_rate':   fetch_fred_rate('FEDFUNDS',      api_key),
        'fetched_at':       datetime.now().strftime('%Y-%m-%d %H:%M'),
    }

    # Derived: required return for high-yield credit
    # (risk-free rate + credit spread = minimum acceptable return)
    context['hy_required_return'] = context['treasury_10y'] + context['hy_spread']
    context['ig_required_return'] = context['treasury_10y'] + context['ig_spread']

    print(f"   ✓ 10Y Treasury:          {context['treasury_10y']:.2f}%")
    print(f"   ✓ 2Y Treasury:           {context['treasury_2y']:.2f}%")
    print(f"   ✓ HY Credit Spread:      {context['hy_spread']:.2f}%")
    print(f"   ✓ IG Credit Spread:      {context['ig_spread']:.2f}%")
    print(f"   ✓ Fed Funds Rate:        {context['fed_funds_rate']:.2f}%")
    print(f"   ✓ HY Required Return:    {context['hy_required_return']:.2f}%")
    print(f"   ✓ IG Required Return:    {context['ig_required_return']:.2f}%")
    print(f"   ✓ Data fetched at:       {context['fetched_at']}")

    return context


# ==============================================================================
# STEP 2 — LOAD EXISTING PHASE 4 OUTPUTS
# ==============================================================================

def load_portfolio() -> pd.DataFrame:
    """Load the loan-level portfolio CSV produced by Phase 4."""
    print("\n[STEP 2] Loading Phase 4 portfolio data...")

    path = Path('data/powerbi/loan_portfolio.csv')
    if not path.exists():
        raise FileNotFoundError(
            "data/powerbi/loan_portfolio.csv not found. Run phase4_fair_value_engine.py first."
        )

    df = pd.read_csv(path)
    print(f"   ✓ Loaded {len(df):,} loans")
    print(f"   ✓ Columns: {list(df.columns)}")
    return df


# ==============================================================================
# STEP 3 — CORE SCORING FUNCTIONS
# ==============================================================================

def compute_ray(int_rate: float, pd_prob: float, lgd: float) -> float:
    """
    Risk-Adjusted Yield (RAY)
    ─────────────────────────
    RAY = Interest Rate − Expected Loss Rate
        = int_rate − (PD × LGD × 100)

    Interpretation:
      RAY > 0   → loan earns more than it loses on average
      RAY < 0   → expected losses exceed interest income → never invest
    """
    expected_loss_rate = pd_prob * lgd * 100
    return round(int_rate - expected_loss_rate, 4)


def compute_excess_spread(ray: float, risk_free_rate: float) -> float:
    """
    Excess Spread = RAY − Risk-Free Rate
    How much extra return you earn above a riskless treasury.
    If negative: you'd be better off buying government bonds.
    """
    return round(ray - risk_free_rate, 4)


def investment_verdict(
    pd_prob: float,
    lgd: float,
    ray: float,
    excess_spread: float,
    grade: str,
) -> dict:
    """
    Returns a BUY / HOLD / AVOID decision with structured reasoning.

    Decision logic (in priority order):
    1. If RAY < 0                         → AVOID (losing money on expected basis)
    2. If excess_spread < 0               → AVOID (worse than risk-free)
    3. If PD > 0.35 or LGD > 0.65        → AVOID (too risky)
    4. If PD ≤ 0.20, RAY ≥ 4, LGD ≤ 0.50 → BUY
    5. Otherwise                          → HOLD
    """
    reasons = []

    # Hard avoids
    if ray < 0:
        reasons.append(f"RAY is negative ({ray:.1f}%) — expected losses exceed interest income")
        return {
            'verdict': 'AVOID',
            'confidence': 'High',
            'reasons': reasons,
            'ray': ray,
            'excess_spread': excess_spread,
        }

    if excess_spread < 0:
        reasons.append(
            f"Excess spread is negative ({excess_spread:.1f}%) — "
            f"treasury bonds offer better risk-adjusted return"
        )
        return {
            'verdict': 'AVOID',
            'confidence': 'High',
            'reasons': reasons,
            'ray': ray,
            'excess_spread': excess_spread,
        }

    if pd_prob > THRESHOLDS['HOLD']['max_pd']:
        reasons.append(f"PD ({pd_prob:.1%}) exceeds maximum threshold ({THRESHOLDS['HOLD']['max_pd']:.0%})")
        return {
            'verdict': 'AVOID',
            'confidence': 'Medium',
            'reasons': reasons,
            'ray': ray,
            'excess_spread': excess_spread,
        }

    if lgd > THRESHOLDS['HOLD']['max_lgd']:
        reasons.append(f"LGD ({lgd:.1%}) exceeds maximum threshold ({THRESHOLDS['HOLD']['max_lgd']:.0%})")
        return {
            'verdict': 'AVOID',
            'confidence': 'Medium',
            'reasons': reasons,
            'ray': ray,
            'excess_spread': excess_spread,
        }

    # BUY conditions
    if (
        pd_prob  <= THRESHOLDS['BUY']['max_pd']
        and ray  >= THRESHOLDS['BUY']['min_ray']
        and lgd  <= THRESHOLDS['BUY']['max_lgd']
    ):
        reasons.append(f"Strong RAY of {ray:.1f}% well above risk-free rate")
        reasons.append(f"Low PD ({pd_prob:.1%}) and contained LGD ({lgd:.1%})")
        if grade in ('A', 'B'):
            reasons.append(f"Grade {grade} — investment grade quality")
        return {
            'verdict': 'BUY',
            'confidence': 'High' if pd_prob < 0.10 else 'Medium',
            'reasons': reasons,
            'ray': ray,
            'excess_spread': excess_spread,
        }

    # HOLD — everything else that passed the avoids
    reasons.append(f"RAY of {ray:.1f}% is positive but moderate")
    reasons.append(f"PD ({pd_prob:.1%}) and LGD ({lgd:.1%}) are within acceptable range")
    return {
        'verdict': 'HOLD',
        'confidence': 'Medium',
        'reasons': reasons,
        'ray': ray,
        'excess_spread': excess_spread,
    }


# ==============================================================================
# STEP 4 — SCORE ENTIRE PORTFOLIO
# ==============================================================================

def score_portfolio(df: pd.DataFrame, market: dict) -> pd.DataFrame:
    """
    Apply RAY, excess spread, and investment verdict to every loan.
    """
    print("\n[STEP 3] Scoring portfolio with investment decisions...")

    risk_free = market['treasury_10y']

    # Compute RAY per loan
    df['ray'] = df.apply(
        lambda r: compute_ray(r['int_rate'], r['pd_prob'], r['lgd']),
        axis=1
    )

    # Compute excess spread
    df['excess_spread'] = df['ray'] - risk_free

    # Investment verdict per loan
    verdicts = df.apply(
        lambda r: investment_verdict(
            r['pd_prob'], r['lgd'], r['ray'],
            r['excess_spread'], r['grade']
        ),
        axis=1
    )

    df['verdict']        = verdicts.apply(lambda v: v['verdict'])
    df['confidence']     = verdicts.apply(lambda v: v['confidence'])
    df['primary_reason'] = verdicts.apply(lambda v: v['reasons'][0])

    # Rank BUY loans by RAY descending
    df['investment_rank'] = df['ray'].rank(ascending=False, method='min').astype(int)

    print(f"   ✓ RAY computed for {len(df):,} loans")
    print(f"   ✓ Risk-free benchmark: {risk_free:.2f}% (10Y Treasury)")

    counts = df['verdict'].value_counts()
    for verdict in ['BUY', 'HOLD', 'AVOID']:
        n = counts.get(verdict, 0)
        pct = n / len(df) * 100
        print(f"   {verdict:<6}: {n:>6,} loans ({pct:.1f}%)")

    return df


# ==============================================================================
# STEP 5 — STRESS TEST VERDICTS
# ==============================================================================

def stress_test_verdicts(df: pd.DataFrame, market: dict) -> pd.DataFrame:
    """
    Re-run investment decisions under each stress scenario.
    Shows how the BUY/HOLD/AVOID breakdown shifts in a recession.
    """
    print("\n[STEP 4] Running stress test on investment decisions...")

    rows = []
    risk_free = market['treasury_10y']

    for scenario, mult in STRESS_MULTIPLIERS.items():
        pd_stressed   = np.clip(df['pd_prob'] * mult['pd'],   0, 0.99)
        lgd_stressed  = np.clip(df['lgd']     * mult['lgd'],  0, 0.95)
        rate_stressed = df['int_rate'] * mult['rate']

        ray_stressed = rate_stressed - (pd_stressed * lgd_stressed * 100)
        excess_stressed = ray_stressed - risk_free

        verdicts = pd.Series([
            investment_verdict(pd, lgd, ray, exc, grade)['verdict']
            for pd, lgd, ray, exc, grade in zip(
                pd_stressed, lgd_stressed,
                ray_stressed, excess_stressed,
                df['grade']
            )
        ])

        counts = verdicts.value_counts()
        rows.append({
            'Scenario':       scenario,
            'BUY_count':      counts.get('BUY',   0),
            'HOLD_count':     counts.get('HOLD',  0),
            'AVOID_count':    counts.get('AVOID', 0),
            'BUY_pct':        round(counts.get('BUY',   0) / len(df) * 100, 1),
            'HOLD_pct':       round(counts.get('HOLD',  0) / len(df) * 100, 1),
            'AVOID_pct':      round(counts.get('AVOID', 0) / len(df) * 100, 1),
            'Avg_RAY':        round(ray_stressed.mean(), 2),
            'Avg_PD':         round(pd_stressed.mean(),  4),
        })

        print(f"   {scenario:<20}: BUY={counts.get('BUY',0):>5,} "
              f"HOLD={counts.get('HOLD',0):>5,} "
              f"AVOID={counts.get('AVOID',0):>5,} "
              f"| Avg RAY={ray_stressed.mean():.2f}%")

    return pd.DataFrame(rows)


# ==============================================================================
# STEP 6 — TOP INVESTABLE LOANS
# ==============================================================================

def get_top_investments(df: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """
    Return the top N BUY-rated loans ranked by RAY.
    These are the specific loans a fund manager would target.
    """
    buys = df[df['verdict'] == 'BUY'].copy()
    buys = buys.sort_values('ray', ascending=False).head(n)

    top = buys[[
        'loan_amnt', 'int_rate', 'grade', 'purpose',
        'pd_prob', 'lgd', 'ray', 'excess_spread',
        'fair_value', 'expected_loss',
        'verdict', 'confidence', 'primary_reason'
    ]].copy()

    top['pd_prob']      = (top['pd_prob'] * 100).round(2)
    top['lgd']          = (top['lgd']     * 100).round(2)
    top['ray']          = top['ray'].round(2)
    top['excess_spread']= top['excess_spread'].round(2)

    top.columns = [
        'Loan Amount', 'Int Rate (%)', 'Grade', 'Purpose',
        'PD (%)', 'LGD (%)', 'RAY (%)', 'Excess Spread (%)',
        'Fair Value ($)', 'Expected Loss ($)',
        'Verdict', 'Confidence', 'Primary Reason'
    ]

    return top.reset_index(drop=True)


# ==============================================================================
# STEP 7 — PORTFOLIO-LEVEL RECOMMENDATION
# ==============================================================================

def portfolio_recommendation(df: pd.DataFrame, market: dict) -> dict:
    """
    Generate a single portfolio-level investment recommendation.
    Summarises the key metrics a fund manager would present to an investment committee.
    """
    buy_df   = df[df['verdict'] == 'BUY']
    hold_df  = df[df['verdict'] == 'HOLD']
    avoid_df = df[df['verdict'] == 'AVOID']

    total_par       = df['loan_amnt'].sum()
    investable_par  = buy_df['loan_amnt'].sum()
    avoid_par       = avoid_df['loan_amnt'].sum()

    avg_ray_buy     = buy_df['ray'].mean()   if len(buy_df)   > 0 else 0
    avg_ray_all     = df['ray'].mean()
    avg_pd_buy      = buy_df['pd_prob'].mean() if len(buy_df) > 0 else 0

    # Overall portfolio health score (0-100)
    # Weighted: 40% from BUY%, 30% from avg RAY vs benchmark, 30% from avoid%
    buy_pct   = len(buy_df)   / len(df)
    avoid_pct = len(avoid_df) / len(df)
    ray_score = min(avg_ray_all / market['hy_required_return'], 1.0) if market['hy_required_return'] > 0 else 0

    health_score = round(
        (buy_pct * 40) + (ray_score * 30) + ((1 - avoid_pct) * 30),
        1
    )

    if health_score >= 60:
        overall = 'INVESTABLE'
        summary = (
            f"Portfolio is investable. {len(buy_df):,} loans ({buy_pct:.1%}) "
            f"meet BUY criteria with an average RAY of {avg_ray_buy:.1f}%. "
            f"Recommended allocation to BUY-rated loans: "
            f"${investable_par:,.0f} ({investable_par/total_par:.1%} of par)."
        )
    elif health_score >= 35:
        overall = 'SELECTIVE'
        summary = (
            f"Portfolio requires selectivity. Only {len(buy_df):,} loans ({buy_pct:.1%}) "
            f"meet BUY criteria. Focus on Grade A-C loans with RAY above "
            f"{market['hy_required_return']:.1f}%. Avoid {avoid_pct:.1%} of portfolio."
        )
    else:
        overall = 'AVOID'
        summary = (
            f"Portfolio is not investable at current pricing. "
            f"{avoid_pct:.1%} of loans are rated AVOID. "
            f"Average RAY of {avg_ray_all:.1f}% is insufficient given "
            f"a {market['hy_required_return']:.1f}% required return."
        )

    return {
        'overall_verdict':    overall,
        'health_score':       health_score,
        'summary':            summary,
        'total_loans':        len(df),
        'buy_count':          len(buy_df),
        'hold_count':         len(hold_df),
        'avoid_count':        len(avoid_df),
        'buy_pct':            round(buy_pct * 100, 1),
        'avoid_pct':          round(avoid_pct * 100, 1),
        'investable_par':     round(investable_par, 0),
        'avoid_par':          round(avoid_par, 0),
        'avg_ray_all':        round(avg_ray_all, 2),
        'avg_ray_buy':        round(avg_ray_buy, 2),
        'avg_pd_buy':         round(avg_pd_buy, 4),
        'risk_free_rate':     market['treasury_10y'],
        'hy_required_return': market['hy_required_return'],
        'as_of':              market['fetched_at'],
    }


# ==============================================================================
# STEP 8 — SINGLE LOAN SCORER (used by FastAPI later)
# ==============================================================================

def score_single_loan(
    loan_amnt: float,
    int_rate: float,
    grade: str,
    annual_inc: float,
    dti: float,
    fico_score: float,
    home_ownership: str,
    purpose: str,
    term_months: int,
    delinq_2yrs: int,
    api_key: str = 'demo'
) -> dict:
    """
    Score a single new loan from raw inputs.
    Loads the latest trained model and scaler, runs the full pipeline,
    and returns a complete investment decision report.

    This function is the core of the FastAPI /api/score endpoint in Phase 6.
    """
    print(f"\n[SINGLE LOAN] Scoring: ${loan_amnt:,.0f} at {int_rate}% | Grade {grade}")

    # Load latest model and scaler
    model_files = sorted(Path('models').glob('xgboost_pd_model_*.pkl'))
    with open(model_files[-1], 'rb') as f:
        model = pickle.load(f)

    with open('data/processed/scaler.pkl', 'rb') as f:
        scaler = pickle.load(f)

    with open('data/processed/feature_names.pkl', 'rb') as f:
        feature_names = pickle.load(f)

    # Build feature vector (must match Phase 2 exactly)
    grade_map    = {'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7}
    purpose_list = ['debt_consolidation','credit_card','home_improvement',
                    'other','major_purchase','small_business','car','medical']

    fico_mid          = fico_score
    fico_range_width  = 10
    loan_to_income    = loan_amnt  / max(annual_inc, 1)
    funded_to_income  = loan_amnt  / max(annual_inc, 1)
    acc_per_year      = 8 / max(annual_inc / 10000, 1)
    has_past_delinq   = int(delinq_2yrs > 0)
    term_60m          = int(term_months == 60)
    high_int_rate     = int(int_rate > 13.0)  # approximate median
    grade_encoded     = grade_map.get(grade.upper(), 4)
    purpose_encoded   = purpose_list.index(purpose) if purpose in purpose_list else -1

    home_MORTGAGE = int(home_ownership.upper() == 'MORTGAGE')
    home_NONE     = int(home_ownership.upper() == 'NONE')
    home_OTHER    = int(home_ownership.upper() == 'OTHER')
    home_OWN      = int(home_ownership.upper() == 'OWN')
    home_RENT     = int(home_ownership.upper() == 'RENT')

    raw_features = {
        'loan_amnt':            loan_amnt,
        'int_rate':             int_rate,
        'grade_encoded':        grade_encoded,
        'dti':                  dti,
        'delinq_2yrs':          delinq_2yrs,
        'fico_mid':             fico_mid,
        'fico_range_width':     fico_range_width,
        'open_acc':             8.0,
        'pub_rec':              0.0,
        'revol_util':           30.0,
        'total_acc':            15.0,
        'loan_to_income':       loan_to_income,
        'funded_to_income':     funded_to_income,
        'has_past_delinquency': has_past_delinq,
        'term_60m':             term_60m,
        'high_int_rate':        high_int_rate,
        'purpose_encoded':      purpose_encoded,
        'home_MORTGAGE':        home_MORTGAGE,
        'home_NONE':            home_NONE,
        'home_OTHER':           home_OTHER,
        'home_OWN':             home_OWN,
        'home_RENT':            home_RENT,
    }

    # Align to model's feature order
    feature_vec = np.array([
        raw_features.get(f, 0.0) for f in feature_names
    ]).reshape(1, -1)

    feature_vec_scaled = scaler.transform(feature_vec)
    pd_prob = float(model.predict_proba(feature_vec_scaled)[0][1])

    # LGD from grade
    lgd_map = {'A':0.25,'B':0.35,'C':0.45,'D':0.55,'E':0.65,'F':0.75,'G':0.85}
    lgd = lgd_map.get(grade.upper(), 0.50)
    if home_ownership.upper() == 'MORTGAGE': lgd -= 0.05
    if home_ownership.upper() == 'RENT':     lgd += 0.10
    if dti > 30: lgd += 0.10
    lgd = float(np.clip(lgd, 0.10, 0.95))

    # Fair value
    survival    = 1.0 - pd_prob
    principal_r = loan_amnt * (survival + pd_prob * (1 - lgd))
    interest_i  = loan_amnt * (int_rate / 100 / 12) * min(term_months, 36) * survival
    fair_value  = max(principal_r + interest_i, loan_amnt * 0.30)
    el          = pd_prob * lgd * loan_amnt

    # Market context
    market  = get_market_context(api_key)
    ray     = compute_ray(int_rate, pd_prob, lgd)
    excess  = compute_excess_spread(ray, market['treasury_10y'])
    verdict = investment_verdict(pd_prob, lgd, ray, excess, grade)

    return {
        'input': {
            'loan_amnt': loan_amnt, 'int_rate': int_rate,
            'grade': grade, 'annual_inc': annual_inc,
            'dti': dti, 'fico_score': fico_score,
        },
        'risk_metrics': {
            'pd_prob':     round(pd_prob, 4),
            'lgd':         round(lgd, 4),
            'expected_loss': round(el, 2),
            'fair_value':  round(fair_value, 2),
            'fair_value_pct': round(fair_value / loan_amnt * 100, 1),
        },
        'investment': {
            'ray':            round(ray, 2),
            'excess_spread':  round(excess, 2),
            'risk_free_rate': market['treasury_10y'],
            'verdict':        verdict['verdict'],
            'confidence':     verdict['confidence'],
            'reasons':        verdict['reasons'],
        },
        'market_context': market,
    }


# ==============================================================================
# STEP 9 — EXPORT ALL OUTPUTS
# ==============================================================================

def export_outputs(
    df_scored: pd.DataFrame,
    stress_df: pd.DataFrame,
    top_investments: pd.DataFrame,
    portfolio_rec: dict,
    market: dict,
):
    """Save all Phase 5 outputs to data/powerbi/ for Power BI and Phase 6."""
    print("\n[STEP 5] Exporting outputs...")

    os.makedirs('data/powerbi', exist_ok=True)
    os.makedirs('outputs', exist_ok=True)

    # 1. Scored loan portfolio (adds verdict columns to existing portfolio)
    df_scored.to_csv('data/powerbi/loan_portfolio_scored.csv', index=False)
    print("   ✓ data/powerbi/loan_portfolio_scored.csv")

    # 2. Stress test verdicts
    stress_df.to_csv('data/powerbi/stress_verdicts.csv', index=False)
    print("   ✓ data/powerbi/stress_verdicts.csv")

    # 3. Top 20 investable loans
    top_investments.to_csv('data/powerbi/top_investments.csv', index=False)
    print("   ✓ data/powerbi/top_investments.csv")

    # 4. Market context snapshot
    pd.DataFrame([market]).to_csv('data/powerbi/market_context.csv', index=False)
    print("   ✓ data/powerbi/market_context.csv")

    # 5. Portfolio recommendation (for FastAPI /api/decide)
    pd.DataFrame([portfolio_rec]).to_csv('data/powerbi/portfolio_recommendation.csv', index=False)
    print("   ✓ data/powerbi/portfolio_recommendation.csv")

    # 6. Full Excel report
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    excel_path = f'outputs/PHASE5_Investment_Report_{ts}.xlsx'

    verdict_summary = df_scored['verdict'].value_counts().reset_index()
    verdict_summary.columns = ['Verdict', 'Count']
    verdict_summary['Pct'] = (verdict_summary['Count'] / len(df_scored) * 100).round(1)

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        pd.DataFrame([portfolio_rec]).to_excel(writer, sheet_name='Portfolio Recommendation', index=False)
        top_investments.to_excel(writer,              sheet_name='Top 20 Investments',       index=False)
        stress_df.to_excel(writer,                    sheet_name='Stress Test Verdicts',     index=False)
        verdict_summary.to_excel(writer,              sheet_name='Verdict Summary',          index=False)
        pd.DataFrame([market]).to_excel(writer,       sheet_name='Market Context',           index=False)
        df_scored.head(500).to_excel(writer,          sheet_name='Sample Scored Loans',      index=False)

    print(f"   ✓ {excel_path}")


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("\n" + "="*70)
    print("PHASE 5: INVESTMENT DECISION ENGINE")
    print("="*70)
    print("Combining ML outputs with live market data to generate")
    print("BUY / HOLD / AVOID signals for every loan in the portfolio.")
    print("="*70)

    # Load FRED API key from environment
    api_key = os.getenv('FRED_API_KEY', 'demo')
    if api_key == 'demo':
        print("\n⚠  FRED_API_KEY not set in .env — using fallback market rates.")
        print("   Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html")

    # Run pipeline
    market          = get_market_context(api_key)
    df              = load_portfolio()
    df_scored       = score_portfolio(df, market)
    stress_df       = stress_test_verdicts(df_scored, market)
    top_investments = get_top_investments(df_scored, n=20)
    portfolio_rec   = portfolio_recommendation(df_scored, market)

    # Export
    export_outputs(df_scored, stress_df, top_investments, portfolio_rec, market)

    # Final summary
    print("\n" + "="*70)
    print("PHASE 5 SUMMARY")
    print("="*70)
    print(f"\n📊 PORTFOLIO VERDICT: {portfolio_rec['overall_verdict']}")
    print(f"   Health Score:      {portfolio_rec['health_score']}/100")
    print(f"\n   {portfolio_rec['summary']}")
    print(f"\n📈 INVESTMENT BREAKDOWN:")
    print(f"   BUY:   {portfolio_rec['buy_count']:>6,} loans ({portfolio_rec['buy_pct']:.1f}%)")
    print(f"   HOLD:  {portfolio_rec['hold_count']:>6,} loans")
    print(f"   AVOID: {portfolio_rec['avoid_count']:>6,} loans ({portfolio_rec['avoid_pct']:.1f}%)")
    print(f"\n💹 MARKET BENCHMARK:")
    print(f"   10Y Treasury:       {market['treasury_10y']:.2f}%")
    print(f"   HY Required Return: {market['hy_required_return']:.2f}%")
    print(f"   Portfolio Avg RAY:  {portfolio_rec['avg_ray_all']:.2f}%")
    print(f"   BUY loans Avg RAY:  {portfolio_rec['avg_ray_buy']:.2f}%")

    print(f"\n🏆 TOP 3 INVESTMENTS:")
    for i, row in top_investments.head(3).iterrows():
        print(f"   {i+1}. ${row['Loan Amount']:>8,.0f} | "
              f"Grade {row['Grade']} | "
              f"RAY {row['RAY (%)']:.1f}% | "
              f"PD {row['PD (%)']:.1f}%")

    print("\n" + "="*70)
    print("✅ PHASE 5 COMPLETE: INVESTMENT DECISION ENGINE READY")
    print("="*70)
    print("\nNext Steps (Phase 6):")
    print("  • Build FastAPI backend exposing score_single_loan() as /api/score")
    print("  • Expose portfolio_recommendation() as /api/decide")
    print("  • Build React frontend consuming these endpoints")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()