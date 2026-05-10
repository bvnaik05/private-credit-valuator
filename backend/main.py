from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import numpy as np
import pickle
import requests
import os
import io
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
import os
os.chdir(Path(__file__).parent.parent)
print(f"Working directory: {os.getcwd()}")

app = FastAPI(
    title="Private Credit Risk & Valuation API",
    description="End-to-end credit risk scoring, fair value estimation, and investment decisions powered by XGBoost and live FRED market data.",
    version="1.0.0"
)

# Allow React frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# LOAD ML ARTIFACTS ON STARTUP
# ==============================================================================

MODEL      = None
SCALER     = None
FEAT_NAMES = None

def load_artifacts():
    global MODEL, SCALER, FEAT_NAMES
    try:
        model_files = sorted(Path("models").glob("xgboost_pd_model_*.pkl"))
        if not model_files:
            raise FileNotFoundError("No model file found in models/")
        with open(model_files[-1], "rb") as f:
            MODEL = pickle.load(f)
        with open("data/processed/scaler.pkl", "rb") as f:
            SCALER = pickle.load(f)
        with open("data/processed/feature_names.pkl", "rb") as f:
            FEAT_NAMES = pickle.load(f)
        print(f"✅ Model loaded: {model_files[-1].name}")
        print(f"✅ Features: {len(FEAT_NAMES)}")
    except Exception as e:
        print(f"⚠ Could not load ML artifacts: {e}")

load_artifacts()

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

FRED_KEY = os.getenv("FRED_API_KEY", "demo")

FALLBACK_RATES = {
    "DGS10":         4.41,
    "DGS2":          3.92,
    "BAMLH0A0HYM2":  2.79,
    "BAMLC0A0CM":    0.79,
    "FEDFUNDS":      3.64,
}

def fetch_fred(series_id: str) -> float:
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={FRED_KEY}"
            f"&file_type=json&limit=1&sort_order=desc"
        )
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            obs = r.json().get("observations", [])
            if obs and obs[0]["value"] != ".":
                return float(obs[0]["value"])
    except Exception:
        pass
    return FALLBACK_RATES.get(series_id, 0.0)


def get_market_rates() -> dict:
    t10  = fetch_fred("DGS10")
    t2   = fetch_fred("DGS2")
    hy   = fetch_fred("BAMLH0A0HYM2")
    ig   = fetch_fred("BAMLC0A0CM")
    fed  = fetch_fred("FEDFUNDS")
    return {
        "treasury_10y":      t10,
        "treasury_2y":       t2,
        "hy_spread":         hy,
        "ig_spread":         ig,
        "fed_funds_rate":    fed,
        "hy_required_return": round(t10 + hy, 2),
        "ig_required_return": round(t10 + ig, 2),
    }


def compute_lgd(grade: str, home_ownership: str, dti: float) -> float:
    base = {"A":0.25,"B":0.35,"C":0.45,"D":0.55,"E":0.65,"F":0.75,"G":0.85}
    lgd  = base.get(grade.upper(), 0.50)
    if home_ownership.upper() == "MORTGAGE": lgd -= 0.05
    if home_ownership.upper() == "RENT":     lgd += 0.10
    if dti > 30: lgd += 0.10
    elif dti > 20: lgd += 0.05
    return float(np.clip(lgd, 0.10, 0.95))


def compute_fair_value(
    loan_amnt: float, int_rate: float,
    pd_prob: float, lgd: float, term_months: int
) -> float:
    survival    = 1.0 - pd_prob
    principal_r = loan_amnt * (survival + pd_prob * (1 - lgd))
    interest_i  = loan_amnt * (int_rate/100/12) * min(term_months, 36) * survival
    return max(principal_r + interest_i, loan_amnt * 0.30)


def make_verdict(
    pd_prob: float, lgd: float,
    ray: float, excess_spread: float, grade: str
) -> dict:
    if ray < 0:
        return {"verdict":"AVOID","confidence":"High",
                "reason":f"RAY is negative ({ray:.1f}%) — losses exceed income"}
    if excess_spread < 0:
        return {"verdict":"AVOID","confidence":"High",
                "reason":f"Excess spread negative — treasury bonds pay more"}
    if pd_prob > 0.35:
        return {"verdict":"AVOID","confidence":"Medium",
                "reason":f"PD {pd_prob:.1%} exceeds 35% threshold"}
    if lgd > 0.65:
        return {"verdict":"AVOID","confidence":"Medium",
                "reason":f"LGD {lgd:.1%} exceeds 65% threshold"}
    if pd_prob <= 0.20 and ray >= 4.0 and lgd <= 0.50:
        return {"verdict":"BUY","confidence":"High",
                "reason":f"Strong RAY {ray:.1f}% with low PD {pd_prob:.1%}"}
    return {"verdict":"HOLD","confidence":"Medium",
            "reason":f"Positive RAY {ray:.1f}% but moderate risk profile"}

    def to_python(obj):
        """Convert numpy types to native Python for JSON serialization"""
        import numpy as np
        if isinstance(obj, (np.integer,)):  return int(obj)
        if isinstance(obj, (np.floating,)): return float(obj)
        if isinstance(obj, (np.ndarray,)):  return obj.tolist()
        return obj

def score_loan_features(
    loan_amnt, int_rate, grade, annual_inc,
    dti, fico_score, home_ownership, purpose,
    term_months, delinq_2yrs
) -> float:
    if MODEL is None:
        raise HTTPException(500, "Model not loaded")

    grade_map    = {"A":1,"B":2,"C":3,"D":4,"E":5,"F":6,"G":7}
    purpose_list = ["debt_consolidation","credit_card","home_improvement",
                    "other","major_purchase","small_business","car","medical"]

    raw = {
        "loan_amnt":            loan_amnt,
        "int_rate":             int_rate,
        "grade_encoded":        grade_map.get(grade.upper(), 4),
        "dti":                  dti,
        "delinq_2yrs":          delinq_2yrs,
        "fico_mid":             fico_score,
        "fico_range_width":     10.0,
        "open_acc":             8.0,
        "pub_rec":              0.0,
        "revol_util":           30.0,
        "total_acc":            15.0,
        "loan_to_income":       loan_amnt / max(annual_inc, 1),
        "funded_to_income":     loan_amnt / max(annual_inc, 1),
        "has_past_delinquency": int(delinq_2yrs > 0),
        "term_60m":             int(term_months == 60),
        "high_int_rate":        int(int_rate > 13.0),
        "purpose_encoded":      purpose_list.index(purpose)
                                if purpose in purpose_list else -1,
        "home_MORTGAGE":        int(home_ownership.upper() == "MORTGAGE"),
        "home_NONE":            int(home_ownership.upper() == "NONE"),
        "home_OTHER":           int(home_ownership.upper() == "OTHER"),
        "home_OWN":             int(home_ownership.upper() == "OWN"),
        "home_RENT":            int(home_ownership.upper() == "RENT"),
    }

    vec = np.array([raw.get(f, 0.0) for f in FEAT_NAMES]).reshape(1, -1)
    vec_scaled = SCALER.transform(vec)
    return float(MODEL.predict_proba(vec_scaled)[0][1])


# ==============================================================================
# REQUEST MODELS
# ==============================================================================

class LoanInput(BaseModel):
    loan_amnt:      float
    int_rate:       float
    grade:          str
    annual_inc:     float
    dti:            float
    fico_score:     float
    home_ownership: str
    purpose:        str = "debt_consolidation"
    term_months:    int = 36
    delinq_2yrs:    int = 0


# ==============================================================================
# ENDPOINTS
# ==============================================================================

@app.get("/")
def root():
    return {
        "name":    "Private Credit Risk & Valuation API",
        "version": "1.0.0",
        "status":  "live",
        "docs":    "/docs",
        "endpoints": [
            "GET  /api/market",
            "POST /api/score",
            "POST /api/portfolio",
            "GET  /api/decide",
        ]
    }


@app.get("/api/market")
def get_market():
    """
    Returns live market rates from FRED.
    Used by the React frontend to show the market context sidebar.
    """
    return get_market_rates()


@app.post("/api/score")
def score_loan(loan: LoanInput):
    """
    Score a single loan from raw inputs.
    Returns: PD, LGD, fair value, expected loss, RAY, BUY/HOLD/AVOID verdict.
    """
    market  = get_market_rates()
    pd_prob = score_loan_features(
        loan.loan_amnt, loan.int_rate, loan.grade,
        loan.annual_inc, loan.dti, loan.fico_score,
        loan.home_ownership, loan.purpose,
        loan.term_months, loan.delinq_2yrs
    )

    lgd        = compute_lgd(loan.grade, loan.home_ownership, loan.dti)
    fair_value = compute_fair_value(
        loan.loan_amnt, loan.int_rate,
        pd_prob, lgd, loan.term_months
    )
    el         = pd_prob * lgd * loan.loan_amnt
    ray        = round(loan.int_rate - (pd_prob * lgd * 100), 4)
    excess     = round(ray - market["treasury_10y"], 4)
    verdict    = make_verdict(pd_prob, lgd, ray, excess, loan.grade)

    return {
        "input":        loan.dict(),
        "risk_metrics": {
            "pd_prob":        round(pd_prob, 4),
            "pd_pct":         round(pd_prob * 100, 2),
            "lgd":            round(lgd, 4),
            "lgd_pct":        round(lgd * 100, 2),
            "expected_loss":  round(el, 2),
            "fair_value":     round(fair_value, 2),
            "fair_value_pct": round(fair_value / loan.loan_amnt * 100, 1),
            "mtm":            round(fair_value - loan.loan_amnt, 2),
        },
        "investment": {
            "ray":            round(ray, 2),
            "excess_spread":  round(excess, 2),
            "verdict":        verdict["verdict"],
            "confidence":     verdict["confidence"],
            "reason":         verdict["reason"],
        },
        "market": market,
    }


@app.post("/api/portfolio")
async def analyse_portfolio(file: UploadFile = File(...)):
    """
    Upload a CSV of loans, get back full portfolio analytics.
    CSV must have columns: loan_amnt, int_rate, grade, annual_inc,
    dti, fico_score, home_ownership, purpose, term_months, delinq_2yrs
    """
    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        raise HTTPException(400, f"Could not parse CSV: {e}")

    required = ["loan_amnt","int_rate","grade","annual_inc","dti",
                "fico_score","home_ownership"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(400, f"Missing columns: {missing}")

    market = get_market_rates()
    rows   = []

    for _, r in df.iterrows():
        try:
            pd_prob = score_loan_features(
                r["loan_amnt"], r["int_rate"], r["grade"],
                r["annual_inc"], r["dti"], r.get("fico_score", 700),
                r["home_ownership"], r.get("purpose","debt_consolidation"),
                int(r.get("term_months", 36)), int(r.get("delinq_2yrs", 0))
            )
            lgd  = compute_lgd(r["grade"], r["home_ownership"], r["dti"])
            fv   = compute_fair_value(
                r["loan_amnt"], r["int_rate"], pd_prob, lgd,
                int(r.get("term_months", 36))
            )
            el   = pd_prob * lgd * r["loan_amnt"]
            ray  = round(r["int_rate"] - (pd_prob * lgd * 100), 4)
            exc  = round(ray - market["treasury_10y"], 4)
            v    = make_verdict(pd_prob, lgd, ray, exc, r["grade"])

            rows.append({
                "loan_amnt":     float(r["loan_amnt"]),
                "int_rate":      float(r["int_rate"]),
                "grade":         str(r["grade"]),
                "pd_prob":       round(float(pd_prob), 4),
                "lgd":           round(float(lgd), 4),
                "fair_value":    round(float(fv), 2),
                "expected_loss": round(float(el), 2),
                "ray":           round(float(ray), 4),
                "verdict":       str(v["verdict"]),
            })
        except Exception as e:
            print(f"Row failed: {e}")
            continue

    if not rows:
        raise HTTPException(400, "No loans could be scored")

    result_df = pd.DataFrame(rows)
    total     = len(result_df)
    counts    = result_df["verdict"].value_counts().to_dict()

    grade_summary = result_df.groupby("grade").agg(
        count=("loan_amnt","count"),
        total_par=("loan_amnt","sum"),
        avg_pd=("pd_prob","mean"),
        avg_ray=("ray","mean"),
        total_fv=("fair_value","sum"),
        total_el=("expected_loss","sum"),
    ).round(4).reset_index()

# Convert all numpy types to native Python for JSON serialization
    grade_summary = grade_summary.astype(object)
    grade_summary = grade_summary.to_dict(orient="records")
    grade_summary = [
        {k: int(v) if hasattr(v, 'item') else v for k, v in row.items()}
        for row in grade_summary
    ]

    return {
    "summary": {
        "total_loans":   int(total),
        "total_par":     round(float(result_df["loan_amnt"].sum()), 2),
        "total_fv":      round(float(result_df["fair_value"].sum()), 2),
        "total_el":      round(float(result_df["expected_loss"].sum()), 2),
        "avg_pd":        round(float(result_df["pd_prob"].mean()), 4),
        "avg_ray":       round(float(result_df["ray"].mean()), 4),
        "buy_count":     int(counts.get("BUY",   0)),
        "hold_count":    int(counts.get("HOLD",  0)),
        "avoid_count":   int(counts.get("AVOID", 0)),
        "buy_pct":       round(float(counts.get("BUY",0)/total*100), 1),
        "avoid_pct":     round(float(counts.get("AVOID",0)/total*100), 1),
    },
    "grade_breakdown": grade_summary,
    "market":          market,
    "loans":           rows,
}


@app.get("/api/decide")
def portfolio_decision():
    """
    Returns the portfolio-level BUY/HOLD/AVOID verdict and
    top 20 investable loans from the Phase 5 output.
    """
    try:
        rec  = pd.read_csv("data/powerbi/portfolio_recommendation.csv")
        top  = pd.read_csv("data/powerbi/top_investments.csv")
        mkt  = pd.read_csv("data/powerbi/market_context.csv")
        stress = pd.read_csv("data/powerbi/stress_verdicts.csv")
        return {
            "recommendation": rec.to_dict(orient="records")[0],
            "top_investments": top.head(20).to_dict(orient="records"),
            "market":          mkt.to_dict(orient="records")[0],
            "stress_scenarios": stress.to_dict(orient="records"),
        }
    except FileNotFoundError:
        raise HTTPException(
            503,
            "Phase 5 outputs not found. Run phase5_investment_decision.py first."
        )