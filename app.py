# ============================================================
#  AI ?貉撌乩?蝡?v2 ???嗆??祉?
#  ?豢?嚗finance | 鞈?摨恬?Google Sheets | ?函蔡嚗treamlit Cloud
# ============================================================

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import requests
import warnings
warnings.filterwarnings("ignore")

# ?? Page config (MUST be first) ?????????????????????????????
st.set_page_config(
    page_title="?? ?貉撌乩?蝡?,
    page_icon="??",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ?? Dark Mode CSS ????????????????????????????????????????????
st.markdown("""
<style>
.stApp{background:#0e1117}
.main .block-container{padding-top:1.2rem;max-width:1400px}
.card{background:#161b27;border:1px solid #252d3e;border-radius:12px;padding:14px 18px;margin-bottom:10px}
.card-label{color:#6b7a99;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.card-val{color:#f0f2f5;font-size:24px;font-weight:800;margin:3px 0}
.card-sub{font-size:13px;color:#6b7a99}
.sec{color:#9b8cff;font-size:15px;font-weight:700;border-left:3px solid #9b8cff;padding:2px 0 2px 10px;margin:18px 0 10px}
.green{color:#00d896}.red{color:#ff4060}.yellow{color:#ffc842}.purple{color:#9b8cff}
.b-buy{background:#002a1a;color:#00d896;border:1px solid #00d896;padding:2px 12px;border-radius:20px;font-weight:700;font-size:12px}
.b-sell{background:#2a0010;color:#ff4060;border:1px solid #ff4060;padding:2px 12px;border-radius:20px;font-weight:700;font-size:12px}
.b-hold{background:#2a1f00;color:#ffc842;border:1px solid #ffc842;padding:2px 12px;border-radius:20px;font-weight:700;font-size:12px}
.news-item{border-left:3px solid #252d3e;padding:8px 14px;margin:5px 0;background:#161b27;border-radius:0 8px 8px 0}
.news-item a{color:#e0e6f0;text-decoration:none;font-size:14px;font-weight:500}
.news-meta{color:#6b7a99;font-size:11px;margin-top:3px}
.risk-h{background:#2a0010;color:#ff4060;padding:1px 8px;border-radius:4px;font-size:12px;font-weight:600}
.risk-m{background:#2a1500;color:#ff8c42;padding:1px 8px;border-radius:4px;font-size:12px;font-weight:600}
.risk-l{background:#002a1a;color:#00d896;padding:1px 8px;border-radius:4px;font-size:12px;font-weight:600}
.stTabs [data-baseweb="tab-list"]{background:#161b27;border-radius:10px;padding:3px;gap:2px}
.stTabs [data-baseweb="tab"]{border-radius:7px;color:#6b7a99;font-weight:600}
.stTabs [aria-selected="true"]{background:#252d3e!important;color:#f0f2f5!important}
[data-testid="stMetricLabel"]{color:#6b7a99!important}
[data-testid="stMetricValue"]{color:#f0f2f5!important}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-thumb{background:#252d3e;border-radius:3px}
</style>
""", unsafe_allow_html=True)


# ????????????????????????????????????????????????????????????
#  DATA FETCHING  (cached)
# ????????????????????????????????????????????????????????????

@st.cache_data(ttl=600)
def get_price(ticker: str, period: str = "1y") -> pd.DataFrame:
    try:
        df = yf.Ticker(ticker).history(period=period)
        if not df.empty:
            df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800)
def get_info(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def get_financials(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        return {
            "q_income":  t.quarterly_income_stmt,
            "a_income":  t.income_stmt,
            "earnings":  t.earnings_history,
        }
    except Exception:
        return {}


# ?? Method A嚗? yfinance 摮?銵刻撌梁? ??????????????????????

@st.cache_data(ttl=3600)
def calc_from_statements(ticker: str) -> dict:
    result = {}
    try:
        t      = yf.Ticker(ticker)
        income = t.quarterly_income_stmt
        bal    = t.quarterly_balance_sheet

        if income is None or income.empty:
            return result

        def find(df, keys):
            for k in keys:
                if k in df.index:
                    return df.loc[k]
            return None

        rev = find(income, ["Total Revenue", "Operating Revenue"])
        gp  = find(income, ["Gross Profit"])
        ni  = find(income, ["Net Income", "Net Income Common Stockholders",
                             "Net Income Including Noncontrolling Interests"])

        if rev is not None:
            r0 = float(rev.iloc[0]) if not pd.isna(rev.iloc[0]) else None
            if r0 and r0 != 0:
                if gp is not None:
                    g0 = float(gp.iloc[0]) if not pd.isna(gp.iloc[0]) else None
                    if g0 is not None:
                        result["grossMargins"] = g0 / r0
                if ni is not None:
                    n0 = float(ni.iloc[0]) if not pd.isna(ni.iloc[0]) else None
                    if n0 is not None:
                        result["profitMargins"] = n0 / r0
            # Revenue YoY嚗?摮??嚗?            if len(rev) >= 5:
                r4 = float(rev.iloc[4]) if not pd.isna(rev.iloc[4]) else None
                if r4 and r4 != 0 and r0:
                    result["revenueGrowth"] = (r0 - r4) / abs(r4)

        # ROE
        if bal is not None and not bal.empty and ni is not None and len(ni) >= 4:
            eq = find(bal, ["Stockholders Equity", "Total Stockholder Equity",
                            "Common Stock Equity", "Total Equity Gross Minority Interest"])
            if eq is not None:
                equity = float(eq.iloc[0]) if not pd.isna(eq.iloc[0]) else None
                ni_vals = [float(v) for v in ni.iloc[:4] if not pd.isna(v)]
                if equity and equity != 0 and ni_vals:
                    result["returnOnEquity"] = sum(ni_vals) / equity

            # 鞎瘥?            debt = find(bal, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
            eq2  = find(bal, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"])
            if debt is not None and eq2 is not None:
                d0 = float(debt.iloc[0]) if not pd.isna(debt.iloc[0]) else None
                e0 = float(eq2.iloc[0]) if not pd.isna(eq2.iloc[0]) else None
                if d0 is not None and e0 and e0 != 0:
                    result["debtToEquity"] = (d0 / e0) * 100

    except Exception:
        pass
    return result


# ?? Method B嚗inMind API 鋆?∟瓷???????????????????????????

@st.cache_data(ttl=3600 * 6)
def get_finmind(stock_id: str) -> dict:
    result = {}
    if not (stock_id.endswith(".TW") or stock_id.endswith(".TWO")):
        return result

    sid = stock_id.replace(".TW", "").replace(".TWO", "")
    try:
        token = st.secrets.get("FINMIND_TOKEN", "")
    except Exception:
        token = ""

    base = "https://api.finmindtrade.com/api/v4/data"

    try:
        params = {"dataset": "TaiwanStockFinancialStatements",
                  "data_id": sid, "start_date": "2023-01-01"}
        if token:
            params["token"] = token
        r = requests.get(base, params=params, timeout=8)
        items = r.json().get("data", [])

        if items:
            df = pd.DataFrame(items)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date", ascending=False)

            def latest(type_name):
                sub = df[df["type"] == type_name]
                return float(sub["value"].iloc[0]) if not sub.empty else None

            rev = latest("Revenue");      gp  = latest("GrossProfit")
            ni  = latest("NetIncome");    eps = latest("EPS")
            roe = latest("ROE")

            if rev and gp and rev != 0:
                result["grossMargins"]  = gp / rev
            if rev and ni and rev != 0:
                result["profitMargins"] = ni / rev
            if eps:
                result["trailingEps"]   = eps
            if roe:
                result["returnOnEquity"] = roe / 100  # FinMind ? % ?詨?

            # ? YoY
            rev_df = df[df["type"] == "Revenue"].head(6)
            if len(rev_df) >= 5:
                r0 = float(rev_df.iloc[0]["value"])
                r4 = float(rev_df.iloc[4]["value"])
                if r4 and r4 != 0:
                    result["revenueGrowth"] = (r0 - r4) / abs(r4)

    except Exception:
        pass
    return result


# ?? ?蔥???皞???????????????????????????????????????????????

def enrich_info(ticker: str, base_info: dict) -> dict:
    """??A + B 憛怨? yfinance info ?征?賣?雿?""
    info = dict(base_info)

    # Method A嚗??蟡券頝?
    for key, val in calc_from_statements(ticker).items():
        if info.get(key) is None and val is not None:
            info[key] = val

    # Method B嚗撠?∴?
    if ticker.endswith(".TW") or ticker.endswith(".TWO"):
        for key, val in get_finmind(ticker).items():
            if info.get(key) is None and val is not None:
                info[key] = val

    return info


@st.cache_data(ttl=1200)
def get_news(ticker: str) -> list:
    try:
        return yf.Ticker(ticker).news[:10]
    except Exception:
        return []


@st.cache_data(ttl=300)
def get_indices() -> list:
    pairs = [("^GSPC","S&P 500"),("^IXIC","NASDAQ"),("^DJI","??"),("^TWII","?啁??"),("^HSI","??")]
    out = []
    for sym, name in pairs:
        try:
            h = yf.Ticker(sym).history(period="2d")
            if len(h) >= 2:
                prev, last = h["Close"].iloc[-2], h["Close"].iloc[-1]
                out.append({"name": name, "price": last, "pct": (last-prev)/prev*100})
        except Exception:
            pass
    return out


def load_gsheets_watchlist() -> tuple:
    """? (ticker?”, ?????"""
    # Step 1: 霈??URL
    try:
        url = st.secrets["GSHEET_CSV_URL"]
    except Exception:
        return [], "??Streamlit Secrets 鋆⊥銝 GSHEET_CSV_URL嚗?蝣箄???瑼?

    if not url or not url.startswith("http"):
        return [], "??GSHEET_CSV_URL 蝬脣??澆?銝迤蝣?

    # Step 2: 霈??CSV
    try:
        df = pd.read_csv(url)
    except Exception as e:
        return [], f"???⊥?霈??Google Sheet CSV嚗str(e)[:80]}"

    # Step 3: ?暹?雿?    cols = list(df.columns)
    # ??Stock_ID嚗??之撠神嚗?    col_match = next((c for c in cols if c.strip().upper() == "STOCK_ID"), None)
    if not col_match:
        return [], f"???曆???Stock_ID 甈?嚗岫蝞”?暹?甈??荔?{cols}"

    tickers = [t.strip().upper() for t in df[col_match].dropna().tolist() if str(t).strip()]
    if not tickers:
        return [], "?? Stock_ID 甈??舐征??隢 Google Sheet 憛怠?∠巨隞??"

    return tickers, f"????敺?Google Sheets 霈??{len(tickers)} 瑼?


# ????????????????????????????????????????????????????????????
#  QUANT ENGINE
# ????????????????????????????????????????????????????????????

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or len(df) < 5:
        return df
    df = df.copy()
    for n in [5, 10, 20, 60]:
        df[f"MA{n}"] = df["Close"].rolling(n).mean()
    df["BB_mid"]   = df["Close"].rolling(20).mean()
    std            = df["Close"].rolling(20).std()
    df["BB_upper"] = df["BB_mid"] + 2 * std
    df["BB_lower"] = df["BB_mid"] - 2 * std
    delta = df["Close"].diff()
    gain  = delta.where(delta > 0, 0).rolling(14).mean()
    loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df["RSI"] = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"]        = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]   = df["MACD"] - df["MACD_signal"]
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
    return df


def tech_signal(df: pd.DataFrame) -> dict:
    empty = {"signal":"N/A","score":0,"details":[],"entry":None,"stop":None,"target":None,"ret5":0,"ret20":0,"rsi":None}
    if df.empty or len(df) < 26:
        return empty
    df  = add_indicators(df)
    cur = df.iloc[-1]
    prv = df.iloc[-2]
    price = cur["Close"]
    score = 0
    det   = []

    ma5, ma20 = cur.get("MA5"), cur.get("MA20")
    pm5, pm20 = prv.get("MA5"), prv.get("MA20")

    if all(v is not None and not pd.isna(v) for v in [ma5, ma20, pm5, pm20]):
        if pm5 < pm20 and ma5 > ma20:
            score += 30; det.append(("暺?鈭文? MA5?A20", "green"))
        elif pm5 > pm20 and ma5 < ma20:
            score -= 30; det.append(("甇颱滿鈭文? MA5?A20", "red"))
        if price > ma20: score += 15; det.append(("蝡??? MA20", "green"))
        else:            score -= 15; det.append(("頝?? MA20", "red"))
        if ma5 > ma20:   score += 10; det.append(("??憭??", "green"))
        else:            score -= 8;  det.append(("??蝛粹??", "red"))

    ma60 = cur.get("MA60")
    if ma60 and not pd.isna(ma60):
        if price > ma60: score += 10; det.append(("蝡?摮?? MA60", "green"))
        else:            score -= 10; det.append(("頝摮?? MA60", "red"))

    rsi = cur.get("RSI")
    if rsi and not pd.isna(rsi):
        if rsi < 30:    score += 20; det.append((f"RSI 頞都 {rsi:.0f}", "green"))
        elif rsi > 70:  score -= 20; det.append((f"RSI 頞眺 {rsi:.0f}", "red"))
        else:           det.append((f"RSI ?亙熒 {rsi:.0f}", "yellow"))

    macd = cur.get("MACD"); msig = cur.get("MACD_signal")
    pmacd = prv.get("MACD"); pmsig = prv.get("MACD_signal")
    if all(v is not None and not pd.isna(v) for v in [macd, msig, pmacd, pmsig]):
        if pmacd < pmsig and macd > msig: score += 20; det.append(("MACD ??", "green"))
        elif pmacd > pmsig and macd < msig: score -= 20; det.append(("MACD 甇餃?", "red"))
        if macd > 0: score += 5

    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    if cur["Volume"] > avg_vol * 1.5:
        if price > prv["Close"]: score += 10; det.append(("??曉之銝撞", "green"))
        else:                    score -= 10; det.append(("??曉之銝?", "red"))

    bb_u = cur.get("BB_upper"); bb_l = cur.get("BB_lower")
    if bb_u and bb_l and not pd.isna(bb_u):
        bb_pct = (price - bb_l) / (bb_u - bb_l) * 100
        if bb_pct < 15:   score += 12; det.append(("閫詨?撣?銝??舀?", "green"))
        elif bb_pct > 85: score -= 12; det.append(("閫詨?撣?銝?憯?", "red"))

    score = max(-100, min(100, score))
    signal = "BUY" if score >= 40 else "SELL" if score <= -30 else "HOLD"

    recent = df.tail(20)
    support, resistance = recent["Low"].min(), recent["High"].max()
    atr = cur.get("ATR") or price * 0.02
    if pd.isna(atr): atr = price * 0.02

    ret5  = (price - df["Close"].iloc[-6]) / df["Close"].iloc[-6] * 100 if len(df) >= 6 else 0
    ret20 = (price - df["Close"].iloc[-21]) / df["Close"].iloc[-21] * 100 if len(df) >= 21 else 0

    return {
        "signal": signal, "score": score, "details": det,
        "entry": round(price, 2), "stop": round(support - atr * 0.5, 2),
        "target": round(price + (price - (support - atr*0.5)) * 2, 2),
        "rsi": rsi if rsi and not pd.isna(rsi) else None,
        "support": support, "resistance": resistance,
        "ret5": ret5, "ret20": ret20,
        "ma5": ma5, "ma20": ma20,
    }


def fund_score(info: dict) -> dict:
    score = 0
    det   = []

    def check(val_key, mul, thresholds, labels, name):
        nonlocal score
        val = info.get(val_key)
        if val is None:
            return
        v = val * mul
        for thresh, pts, color, label in thresholds:
            if v >= thresh:
                score += pts
                det.append((f"{name} {v:.1f}{labels}", color, label))
                return
        det.append((f"{name} {v:.1f}{labels}", "red", "??"))

    check("returnOnEquity", 100, [(20,25,"green","?芰???0%"),(15,18,"green","?臬末??5%"),(8,8,"yellow","?桅?-15%")], "%", "ROE")
    check("grossMargins",   100, [(50,20,"green","霅瑕?瘝喇50%"),(30,12,"green","?臬末??0%"),(15,5,"yellow","?桅?)], "%", "瘥??)
    check("revenueGrowth",  100, [(25,25,"green","擃??猾25%"),(10,15,"green","蝛拙??0%"),(0,5,"yellow","蝺拇???)], "%", "?撟游?")
    check("profitMargins",  100, [(20,15,"green","擃瞏手20%"),(8,8,"yellow","?桅?)], "%", "瘛典??)

    de = info.get("debtToEquity")
    if de is not None:
        if de < 30:    score += 15; det.append((f"鞎瘥?{de:.0f}%", "green", "鞎∪?蝛拙"))
        elif de < 100: score += 5;  det.append((f"鞎瘥?{de:.0f}%", "yellow", "?拐葉"))
        else:          score -= 10; det.append((f"鞎瘥?{de:.0f}%", "red", "擃?獢?))

    cr = info.get("currentRatio")
    if cr:
        if cr >= 2:   score += 10; det.append((f"瘚?瘥?{cr:.1f}", "green", "瘚??找蔔"))
        elif cr >= 1: score += 5;  det.append((f"瘚?瘥?{cr:.1f}", "yellow", "撠"))
        else:         score -= 10; det.append((f"瘚?瘥?{cr:.1f}", "red", "瘚??批榆"))

    return {"score": max(0, min(100, score)), "details": det}


def peg_model(info: dict) -> dict:
    r = {"peg": None, "fair_value": None, "verdict": "鞈?銝雲",
         "current": None, "pe": None, "pb": None, "ps": None, "fwd_pe": None, "eps": None}
    try:
        r["current"] = info.get("currentPrice") or info.get("regularMarketPrice")
        r["pe"]      = info.get("trailingPE")
        r["pb"]      = info.get("priceToBook")
        r["ps"]      = info.get("priceToSalesTrailing12Months")
        r["fwd_pe"]  = info.get("forwardPE")
        r["eps"]     = info.get("trailingEps")
        grow = info.get("earningsGrowth") or info.get("revenueGrowth")
        if r["pe"] and grow and grow > 0:
            g = grow * 100
            r["peg"] = round(r["pe"] / g, 2)
            if r["eps"]: r["fair_value"] = round(g * r["eps"], 2)
            p = r["peg"]
            if p < 0.5:   r["verdict"] = "?湧?雿摯 ?"
            elif p < 0.8: r["verdict"] = "雿摯 ?"
            elif p < 1.2: r["verdict"] = "?? ?"
            elif p < 2.0: r["verdict"] = "?眼 ??"
            else:          r["verdict"] = "擃摯 ?"
    except Exception:
        pass
    return r


def risk_scan(info: dict, df: pd.DataFrame) -> list:
    risks = []
    pe = info.get("trailingPE")
    if pe:
        if pe > 50:   risks.append(("?祉?瘥?{:.0f}x 璆菟?".format(pe), "h", "?脣?乩?皛??∪頝?敺之"))
        elif pe > 30: risks.append(("?祉?瘥?{:.0f}x ??".format(pe), "m", "隡啣澆歇??憭憟賣???))
    de = info.get("debtToEquity")
    if de:
        if de > 150: risks.append(("鞎瘥?{:.0f}% ??".format(de), "h", "??啣?鞎∪?憯?憭?))
        elif de > 80: risks.append(("鞎瘥?{:.0f}% 銝剔?".format(de), "m", "???閫撖?))
    rg = info.get("revenueGrowth")
    if rg and rg < -0.05: risks.append(("?銵圈 {:.1f}%".format(rg*100), "h", "?箸?Ｘ????))
    si = info.get("shortPercentOfFloat")
    if si:
        if si > 0.15: risks.append(("蝛粹雿?? {:.1f}%".format(si*100), "h", "憭折??征蝐Ⅳ"))
        elif si > 0.08: risks.append(("蝛粹雿?? {:.1f}%".format(si*100), "m", "銝摰?蝛箏???))
    beta = info.get("beta")
    if beta:
        if beta > 2:   risks.append((f"Beta {beta:.2f} 擃郭??, "h", "瞍脰??臬之?文?誑銝?))
        elif beta > 1.5: risks.append((f"Beta {beta:.2f} 銝剝?瘜Ｗ?", "m", "瘥之?斗?"))
    h52 = info.get("fiftyTwoWeekHigh"); l52 = info.get("fiftyTwoWeekLow")
    curr = info.get("currentPrice") or info.get("regularMarketPrice")
    if h52 and l52 and curr and (h52 - l52) > 0:
        pos = (curr - l52) / (h52 - l52) * 100
        if pos > 90: risks.append(("?亥?52?梢?暺?{:.0f}%".format(pos), "m", "?剔?銝?餃?憭?))
    if not df.empty and len(df) >= 60:
        df_i = add_indicators(df)
        ma60 = df_i["MA60"].iloc[-1]
        p    = df_i["Close"].iloc[-1]
        if not pd.isna(ma60) and p < ma60:
            risks.append(("?∪頝摮?? MA60", "m", "銝剜?頞典韏啣摹"))
    if not risks:
        risks.append(("?芰?暸?憭扯郎蝷?, "l", "隞???餈質馱?箸??))
    return risks


def composite(tech: dict, fund: dict, peg: dict) -> tuple:
    t = tech["score"]
    f = fund["score"]
    adj = 0
    pv = peg.get("peg")
    if pv:
        if pv < 0.8:   adj = 15
        elif pv > 2.5: adj = -20
        elif pv > 1.5: adj = -10
    total = t * 0.35 + f * 0.55 + adj * 10
    if total >= 65:   return "撘瑕?鞎琿???", "#00d896"
    elif total >= 45: return "?澆??釣 ??", "#4ecf8c"
    elif total >= 25: return "閫????, "#ffc842"
    elif total >= 5:  return "雓寞? ??", "#ff8c42"
    else:              return "撱箄降?輸? ?", "#ff4060"


# ????????????????????????????????????????????????????????????
#  PLAIN LANGUAGE ANALYSIS  (?唳??質店??
# ????????????????????????????????????????????????????????????

def plain_analysis(ticker: str, info: dict, tech: dict, fund: dict, peg: dict) -> dict:
    name     = info.get("shortName", ticker)
    sector   = info.get("sector", "") or ""
    industry = info.get("industry", "") or ""
    mc       = info.get("marketCap", 0) or 0
    mc_str   = f"${mc/1e9:.0f}B ?之??? if mc > 10e9 else f"${mc/1e9:.1f}B ?葉??? if mc > 1e9 else "撠??砍"

    roe   = (info.get("returnOnEquity") or 0) * 100
    gm    = (info.get("grossMargins") or 0) * 100
    rev_g = (info.get("revenueGrowth") or 0) * 100
    de    = info.get("debtToEquity") or 0
    beta  = info.get("beta") or 1
    pv    = peg.get("peg")
    ts    = tech["score"]
    fs    = fund["score"]

    # ?? ?砍銝?亥店隞晶 ??????????????????????????????????????
    sector_zh = {
        "Technology":"蝘?","Healthcare":"?怎?","Financial Services":"??",
        "Consumer Cyclical":"瘨祥","Industrials":"撌交平","Energy":"?賣?",
        "Communication Services":"??","Utilities":"?祉鈭平",
        "Basic Materials":"???,"Real Estate":"?踹??,
    }.get(sector, sector)
    intro = f"{name} ?臭?摰?{mc_str}嚗惇??{sector_zh or sector} ?Ｘ平??{industry or '?砍'}??

    # ?? ?撞閫漲 ????????????????????????????????????????????
    bull = []
    if rev_g > 20:   bull.append(f"?? ?撟游? {rev_g:.0f}%嚗平蝮曄?梧?隞?”頞?頞?鈭箄眺摰??Ｗ?")
    elif rev_g > 5:  bull.append(f"?? ?撟游? {rev_g:.0f}%嚗帘摰??瑚葉")
    if roe > 20:     bull.append(f"? ROE {roe:.0f}%嚗?詨???Ｚ竟?ｇ???擃?)
    elif roe > 15:   bull.append(f"? ROE {roe:.0f}%嚗?抵????)
    if gm > 50:      bull.append(f"? 瘥??{gm:.0f}%嚗風?眾敺楛嚗鈭箏???韏啣?????)
    elif gm > 30:    bull.append(f"??瘥??{gm:.0f}%嚗?銝摰?摰?賢?")
    if ts >= 30:     bull.append("?? ?銵??嚗??寡粥?Ｗ?撘瘀?撣靽∪?頞?)
    if pv and pv < 1: bull.append(f"? PEG {pv:.1f}嚗???漲靘牧?∪??靘踹?")
    if de < 30:       bull.append(f"?儭?鞎瘥?{de:.0f}%嚗瓷??蝛抬?銝捆???云憭???")
    if not bull:      bull.append("?桀?甇?閮?銝?憿荔?撱箄降閫撖?銝摮?瓷??)

    # ?? ??閫漲 ????????????????????????????????????????????
    bear = []
    if rev_g < 0:    bear.append(f"?? ?撟游? {rev_g:.0f}%嚗平蝮曉蝮格偌嚗?瘜冽?")
    if roe < 8:      bear.append(f"?? ROE {roe:.0f}%嚗?貉竟?Ｘ???雿??航蝡嗥憯?憭?)
    if gm < 20:      bear.append(f"?? 瘥??{gm:.0f}%嚗?拍征??嚗撞????寥敺")
    if ts <= -20:    bear.append("?? ?銵韏啣摹嚗??賜匱蝥?頝??脣閬牲??)
    if pv and pv > 2.5: bear.append(f"? PEG {pv:.1f}嚗?孵歇??敺?璅???嚗??平蝮曆?憒???頝?憭?)
    if de > 100:     bear.append(f"?? 鞎瘥?{de:.0f}%嚗?敺??ｇ??拍?擃????之")
    if beta > 1.8:   bear.append(f"? Beta {beta:.1f}嚗?∠巨敺捆?之瞍脣之頝?撠???敶梢?斗")
    if not bear:     bear.append("?桀?瘝??＊鞎霅衣內嚗?撣瘞賊???憭拚?嚗???all-in")

    # ?? 銝剔?摰Ｚ? ????????????????????????????????????????????
    neutral = [
        f"蝬?閰?嚗?祇 {fs}/100 | ?銵 {ts:+d}??,
        f"隡啣潸?蝝?{peg.get('verdict', '鞈?銝雲')}",
    ]
    fv = peg.get("fair_value")
    curr = info.get("currentPrice") or info.get("regularMarketPrice")
    if fv and curr:
        upside = (fv - curr) / curr * 100
        neutral.append(f"?寞? PEG 璅∪?嚗??摯?潛? ${fv:.2f}嚗'瘥?寥???' + f'{upside:.0f}% 銝?蝛粹?' if upside > 0 else '?曉撌脤??澆??摯??' + f'{-upside:.0f}%'}")
    neutral.append("?? 隞颱????賣?靘琿?嚗遣霅啣??寡眺?乓?嗅?∩?頞?蝮質??? 10%")

    return {"intro": intro, "bull": bull, "bear": bear, "neutral": neutral}


# ????????????????????????????????????????????????????????????
#  MARKET NEWS FEED
# ????????????????????????????????????????????????????????????

def _parse_news_item(item) -> dict:
    """敺?蝔?yfinance ?啗??澆?銝剜??title/link/ts/pub嚗???dict ??{}??""
    title = link = pub = ""
    ts = 0
    try:
        if isinstance(item, dict):
            # ?唳撘?{"type":"STORY","content":{...}}
            c = item.get("content")
            if isinstance(c, dict):
                title = c.get("title", "")
                for key in ("canonicalUrl", "clickThroughUrl"):
                    u = c.get(key)
                    if isinstance(u, dict) and u.get("url"):
                        link = u["url"]; break
                prov = c.get("provider") or c.get("publisher") or {}
                pub  = (prov.get("displayName") or prov.get("name", "")) if isinstance(prov, dict) else str(prov)
                ts_str = c.get("pubDate") or c.get("displayTime") or ""
                if ts_str:
                    try:
                        ts = int(datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp())
                    except Exception:
                        ts = 0
            # ?撘?{"title":"...","link":"...","providerPublishTime":...}
            if not title:
                title = item.get("title") or item.get("headline") or ""
                link  = item.get("link") or item.get("url") or "#"
                ts    = item.get("providerPublishTime") or item.get("publishTime") or 0
                pub_r = item.get("publisher") or item.get("source") or ""
                pub   = pub_r if isinstance(pub_r, str) else (pub_r.get("name","") if isinstance(pub_r,dict) else "")
        else:
            # NewsArticle ?拐辣?澆?
            title = str(getattr(item, "title", "") or "")
            link  = str(getattr(item, "link", "") or getattr(item, "url", "") or "#")
            ts    = getattr(item, "providerPublishTime", 0) or 0
            pub_r = getattr(item, "publisher", "") or ""
            pub   = pub_r if isinstance(pub_r, str) else getattr(pub_r, "name", "")
            if not title and hasattr(item, "content"):
                c2 = item.content
                title = (c2.get("title","") if isinstance(c2,dict) else getattr(c2,"title","")) or ""
    except Exception:
        pass
    if not title:
        return {}
    return {"title": str(title), "link": str(link) or "#",
            "providerPublishTime": int(ts) if ts else 0, "publisher": str(pub)}


@st.cache_data(ttl=1800)
def get_market_news() -> list:
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime

    US_SRC = ["^GSPC","^IXIC","NVDA","AAPL","META","TSLA","MSFT","AMD","GOOGL","AMZN"]
    TW_SRC = ["^TWII","2330.TW","2317.TW","2454.TW","2308.TW","2412.TW",
              "2303.TW","3711.TW","0050.TW","2882.TW","2881.TW","3008.TW"]
    all_news = []

    # --- ?寞? A嚗finance .news嚗???+ ?啗嚗?--
    for src in US_SRC + TW_SRC:
        try:
            raw = yf.Ticker(src).news or []
            for item in list(raw)[:4]:
                parsed = _parse_news_item(item)
                if parsed:
                    parsed["_src"] = src
                    all_news.append(parsed)
        except Exception:
            pass

    def _fetch_rss(url: str, src: str, limit: int = 4):
        try:
            r = requests.get(url, timeout=7, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                return
            root = ET.fromstring(r.content)
            for el in root.findall(".//item")[:limit]:
                title = el.findtext("title") or ""
                link  = el.findtext("link") or "#"
                pub   = el.findtext("source") or ""
                ts = 0
                try:
                    ts = int(parsedate_to_datetime(el.findtext("pubDate") or "").timestamp())
                except Exception:
                    pass
                if title:
                    all_news.append({"title": title, "link": link,
                                     "providerPublishTime": ts, "publisher": pub, "_src": src})
        except Exception:
            pass

    # --- ?寞? B嚗ahoo Finance RSS嚗??∴?---
    us_count = sum(1 for n in all_news if n["_src"] in set(US_SRC))
    if us_count < 5:
        for sym, src in [("%5EGSPC","^GSPC"),("NVDA","NVDA"),("AAPL","AAPL"),
                          ("TSLA","TSLA"),("MSFT","MSFT"),("META","META"),("AMD","AMD")]:
            _fetch_rss(
                f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US",
                src)

    # --- ?寞? C嚗ahoo Finance RSS嚗?∴?蝜葉嚗?--
    tw_count = sum(1 for n in all_news if n["_src"] in set(TW_SRC))
    if tw_count < 5:
        for sym, src in [("2330.TW","2330.TW"),("2317.TW","2317.TW"),
                          ("2454.TW","2454.TW"),("%5ETWII","^TWII"),
                          ("2308.TW","2308.TW"),("2303.TW","2303.TW"),
                          ("0050.TW","0050.TW"),("2882.TW","2882.TW"),
                          ("3008.TW","3008.TW"),("3711.TW","3711.TW")]:
            _fetch_rss(
                f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=TW&lang=zh-Hant-TW",
                src)

    seen, unique = set(), []
    for item in all_news:
        title = item.get("title", "")
        if title and title not in seen:
            seen.add(title)
            unique.append(item)
    unique.sort(key=lambda x: x.get("providerPublishTime", 0), reverse=True)
    return unique[:40]


@st.cache_data(ttl=3600)
def gemini_news_summary(headlines_text: str) -> str:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        return ""
    if not api_key:
        return ""
    prompt = f"""隞乩??臭??亥瓷蝬??憿?銝剛?毽??嚗??函?擃葉???

?啗?璅?嚗?{headlines_text}

隢撓?箔???憛?

?? 隞??鈭辣
嚗???3-5 ???????游???瘥?銝銵?30摮誑?改??具Ｕ??哨?

?? ?湧?撣??
嚗??亥店嚗?憭?/ ?征 / ?嚗蒂隤芣?銝餉???嚗?
?? ?澆?瘜冽?
嚗?-2??鞈犖??孵?釣?◢?芣?璈?嚗?暺?銵??具Ｕ??哨?

閬?嚗?擃葉?陛瞏???蟡冽?霈"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 600},
    }
    models_to_try = [
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
    ]
    last_error = ""
    for model in models_to_try:
        try:
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={api_key}"
            )
            r = requests.post(url, json=payload, timeout=20)
            if r.status_code == 200:
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            last_error = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as e:
            last_error = str(e)[:200]
            continue
    return f"[DEBUG] {last_error}"


# ????????????????????????????????????????????????????????????
#  CHARTS
# ????????????????????????????????????????????????????????????

def price_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    df = add_indicators(df)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.60, 0.20, 0.20], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="K蝺?,
        increasing=dict(line_color="#00d896", fillcolor="#00d896"),
        decreasing=dict(line_color="#ff4060", fillcolor="#ff4060"),
    ), row=1, col=1)
    for ma, c, n in [("MA5","#ffc842","MA5"),("MA20","#9b8cff","MA20"),("MA60","#ff8c42","MA60")]:
        if ma in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=n,
                line=dict(color=c, width=1.3)), row=1, col=1)
    if "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], name="BB銝?,
            line=dict(color="#3d4f70", width=0.8, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], name="BB銝?,
            line=dict(color="#3d4f70", width=0.8, dash="dot"),
            fill="tonexty", fillcolor="rgba(61,79,112,0.08)"), row=1, col=1)
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
            line=dict(color="#9b8cff", width=1.5)), row=2, col=1)
        for lvl, c in [(70,"#ff4060"),(30,"#00d896")]:
            fig.add_hline(y=lvl, line_dash="dot", line_color=c, opacity=0.5, row=2, col=1)
    if "MACD" in df.columns:
        hc = ["#00d896" if v >= 0 else "#ff4060" for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="MACD??,
            marker_color=hc, opacity=0.8), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
            line=dict(color="#ffc842", width=1.3)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="閮?",
            line=dict(color="#ff8c42", width=1.3)), row=3, col=1)
    fig.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#131822",
        font=dict(color="#6b7a99", size=11),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.02),
        xaxis_rangeslider_visible=False,
        height=540, margin=dict(t=30, b=10, l=0, r=0),
        title=dict(text=ticker, font=dict(color="#f0f2f5", size=14), x=0.01),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor="#1a2035", zeroline=False, row=i, col=1)
        fig.update_yaxes(gridcolor="#1a2035", zeroline=False, row=i, col=1)
    return fig


def comparison_chart(data: list) -> go.Figure:
    fig = go.Figure()
    colors = ["#9b8cff","#00d896","#ffc842","#ff8c42"]
    for i, (tkr, df) in enumerate(data):
        if not df.empty:
            norm = (df["Close"] / df["Close"].iloc[0] - 1) * 100
            fig.add_trace(go.Scatter(x=df.index, y=norm, name=tkr,
                line=dict(color=colors[i % 4], width=2)))
    fig.update_layout(
        paper_bgcolor="#0e1117", plot_bgcolor="#131822",
        font=dict(color="#6b7a99"), height=340,
        yaxis_title="?詨??梢??(%)",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=20, b=10, l=0, r=0),
    )
    fig.update_xaxes(gridcolor="#1a2035"); fig.update_yaxes(gridcolor="#1a2035")
    return fig


# ????????????????????????????????????????????????????????????
#  UI HELPERS
# ????????????????????????????????????????????????????????????

def badge(signal: str) -> str:
    m = {"BUY": '<span class="b-buy">BUY ??/span>',
         "SELL":'<span class="b-sell">SELL ??/span>',
         "HOLD":'<span class="b-hold">HOLD</span>'}
    return m.get(signal, signal)


def card(label, value, sub="", color="#f0f2f5"):
    return (f'<div class="card"><div class="card-label">{label}</div>'
            f'<div class="card-val" style="color:{color}">{value}</div>'
            f'<div class="card-sub">{sub}</div></div>')


def fmt(v, spec=".2f", pre="", suf=""):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "??
    return f"{pre}{v:{spec}}{suf}"


def sec(title):
    st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)


# ????????????????????????????????????????????????????????????
#  MAIN
# ????????????????????????????????????????????????????????????

def main():
    st.markdown("# ?? AI ?貉撌乩?蝡?)
    st.caption(f"?豢?靘?嚗ahoo Finance 繚 ?湔 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Index bar
    indices = get_indices()
    if indices:
        cols = st.columns(len(indices))
        for col, idx in zip(cols, indices):
            c = "#00d896" if idx["pct"] >= 0 else "#ff4060"
            col.markdown(
                f'<div class="card" style="text-align:center;padding:10px">'
                f'<div class="card-label">{idx["name"]}</div>'
                f'<div style="color:#f0f2f5;font-size:20px;font-weight:800">{idx["price"]:,.0f}</div>'
                f'<div style="color:{c};font-weight:700">{"?? if idx["pct"]>=0 else "??} {idx["pct"]:+.2f}%</div>'
                f'</div>', unsafe_allow_html=True)

    # ?? 憸冽蝝敺?????????????????????????????????????????????
    st.markdown("""
<div style="background:#1a0a00;border:1px solid #ff8c42;border-radius:12px;padding:12px 18px;margin:12px 0">
<div style="color:#ff8c42;font-weight:700;font-size:13px;margin-bottom:6px">??憸冽蝝敺???瘥活鞎瑁??銝銝?</div>
<div style="color:#c8a87a;font-size:12px;line-height:1.8">
? ?桐??∠巨銝??蜇鞈? <b>10%</b>&nbsp;&nbsp;
?? ?扳???<b>-8%</b> 銝摰???銝&nbsp;&nbsp;
?? ?脣頞? <b>+30%</b> ?都銝?鋡?nbsp;&nbsp;
?? 憭扯?????鞈?嚗???Ⅱ隤???</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    tabs = st.tabs([
        "?? ??弦","?? ?芷?⊥???,"?? 鞎瑕瘙箇?","?? 鞈?瘙箇?",
        "?? ?∠巨瘥?","? 憸券?","? ??蝯?","?? 鞎∪閫??",
        "???瑟???","?? 銝駁?皜","? 隞?啗?",
    ])

    # ??????????????????????????????????????????????????????
    # TAB 1: ??弦
    # ??????????????????????????????????????????????????????
    with tabs[0]:
        c1, c2 = st.columns([3, 1])
        ticker = c1.text_input("?∠巨隞??", "AAPL", key="t1",
            help="蝢: AAPL | ?啗: 2330.TW").strip().upper()
        period = c2.selectbox("???, ["3mo","6mo","1y","2y","5y"], index=2, label_visibility="hidden")

        if ticker:
            with st.spinner("頛銝?.."):
                info = enrich_info(ticker, get_info(ticker))
                df   = get_price(ticker, period)
                news = get_news(ticker)

            if df.empty:
                st.error(f"?曆???`{ticker}`嚗?∟???.TW嚗? 2330.TW嚗?); return

            tech = tech_signal(df)
            fund = fund_score(info)
            peg  = peg_model(info)
            sig, sig_c = composite(tech, fund, peg)

            price = info.get("currentPrice") or info.get("regularMarketPrice") or df["Close"].iloc[-1]
            name  = info.get("shortName", ticker)

            c1,c2,c3,c4,c5 = st.columns(5)
            for col, lbl, val, sub, clr in [
                (c1, "?曉", f"{price:.2f}", info.get("currency","USD"), "#f0f2f5"),
                (c2, "5?交撞頝?, f"{tech['ret5']:+.1f}%", f"20??{tech['ret20']:+.1f}%",
                    "#00d896" if tech['ret5']>=0 else "#ff4060"),
                (c3, "?銵???, f"{tech['score']:+d}", badge(tech["signal"]), "#f0f2f5"),
                (c4, "?箸??, f"{fund['score']}/100", peg.get("verdict",""), "#f0f2f5"),
                (c5, "蝬?撱箄降", sig, peg.get("verdict",""), sig_c),
            ]:
                col.markdown(card(lbl, val, sub, clr), unsafe_allow_html=True)

            st.plotly_chart(price_chart(df, ticker), use_container_width=True)

            # ?? ?唳??質店??閫漲?? ??????????????????????????
            pa = plain_analysis(ticker, info, tech, fund, peg)
            with st.expander("??????唳??ㄐ嚗閰望?閫??嚗?瞍?/ ?? / 銝剔?嚗?, expanded=True):
                st.markdown(f"**{pa['intro']}**")
                col_b, col_s, col_n = st.columns(3)
                with col_b:
                    st.markdown('<div style="background:#002a1a;border-radius:10px;padding:12px;min-height:160px">'
                                '<div style="color:#00d896;font-weight:700;margin-bottom:8px">?? ?撞閫漲</div>', unsafe_allow_html=True)
                    for pt in pa["bull"]:
                        st.markdown(f'<div style="color:#c0f0e0;font-size:13px;margin-bottom:6px">{pt}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with col_s:
                    st.markdown('<div style="background:#2a0010;border-radius:10px;padding:12px;min-height:160px">'
                                '<div style="color:#ff4060;font-weight:700;margin-bottom:8px">?? ??閫漲</div>', unsafe_allow_html=True)
                    for pt in pa["bear"]:
                        st.markdown(f'<div style="color:#f0c0c0;font-size:13px;margin-bottom:6px">{pt}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with col_n:
                    st.markdown('<div style="background:#1a1a2a;border-radius:10px;padding:12px;min-height:160px">'
                                '<div style="color:#9b8cff;font-weight:700;margin-bottom:8px">?? 銝剔?摰Ｚ?</div>', unsafe_allow_html=True)
                    for pt in pa["neutral"]:
                        st.markdown(f'<div style="color:#c0c0e0;font-size:13px;margin-bottom:6px">{pt}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

            t1,t2,t3,t4,t5 = st.tabs(["?銵?,"?箸??,"隡啣?,"?啗?","?砍"])

            with t1:
                la, ra = st.columns(2)
                dfi = add_indicators(df); cur = dfi.iloc[-1]
                with la:
                    sec("????璅?)
                    for ma_n, ma_k in [("MA5","MA5"),("MA20","MA20"),("MA60","MA60")]:
                        v = cur.get(ma_k)
                        if v and not pd.isna(v):
                            delta_str = "蝡? ?? if price > v else "頝 ??
                            st.metric(ma_n, f"{v:.2f}", delta_str)
                    rsi = cur.get("RSI")
                    if rsi and not pd.isna(rsi):
                        st.metric("RSI", f"{rsi:.1f}",
                            "頞眺" if rsi>70 else "頞都" if rsi<30 else "?亙熒?")
                with ra:
                    sec("閮??敦")
                    for lbl, clr in tech["details"]:
                        icon = "?" if clr=="green" else "?" if clr=="red" else "?"
                        st.markdown(f"{icon} {lbl}")
                    st.markdown("---")
                    st.markdown(f"**?脣暺?*嚗{tech['entry']}`")
                    st.markdown(f"**甇Ｘ?暺?*嚗{tech['stop']}`嚗??游??Ｗ嚗?)
                    st.markdown(f"**?格?雿?*嚗{tech['target']}`嚗?:1 憸典瘥?")

            with t2:
                la, ra = st.columns(2)
                with la:
                    sec("鞎∪???")
                    for lbl, clr, desc in fund["details"]:
                        icon = "?? if clr=="green" else "?? if clr=="red" else "?"
                        st.markdown(f"{icon} **{lbl}** ??{desc}")
                with ra:
                    sec("?砍?豢?")
                    mc = info.get("marketCap")
                    st.metric("撣?, f"${mc/1e9:.1f}B" if mc and mc>1e9 else fmt(mc,",.0f","$"))
                    st.metric("?Ｘ平", info.get("industry","??))
                    st.metric("?踹?", info.get("sector","??))
                    emp = info.get("fullTimeEmployees")
                    st.metric("?∪極??, f"{emp:,}" if emp else "??)

            with t3:
                la, ra = st.columns(2)
                with la:
                    sec("PEG 隡啣?)
                    st.metric("?祉?瘥?P/E",    fmt(peg.get("pe"), ".1f", suf="x"))
                    st.metric("PEG 瘥?",      fmt(peg.get("peg"),".2f"))
                    st.metric("?∪瘛典潭? P/B", fmt(peg.get("pb"), ".2f", suf="x"))
                    st.metric("P/S 瘥?,        fmt(peg.get("ps"), ".2f", suf="x"))
                with ra:
                    sec("隡啣潛?隢?)
                    fv = peg.get("fair_value")
                    if fv:
                        upside = (fv - price) / price * 100
                        st.metric("??隡啣?(PEG=1)", f"{fv:.2f}",
                            f"{'銝?' if upside>0 else '銝?'} {upside:+.1f}%")
                    st.metric("隡啣潸?蝝?, peg.get("verdict","??))
                    st.caption("PEG<0.8 雿摯 | 0.8-1.2 ?? | >2 擃摯\n????= EPS ? ???")

            with t4:
                sec("??啗瓷蝬??)
                for item in (news or []):
                    title = item.get("title","")
                    link  = item.get("link","#")
                    pub   = item.get("publisher","")
                    ts    = item.get("providerPublishTime",0)
                    dt    = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M") if ts else ""
                    st.markdown(
                        f'<div class="news-item">'
                        f'<div><a href="{link}" target="_blank">{title}</a></div>'
                        f'<div class="news-meta">{pub} 繚 {dt}</div></div>',
                        unsafe_allow_html=True)
                if not news:
                    st.info("?怎?啗?")

            with t5:
                sec("?砍璁?")
                desc = info.get("longBusinessSummary","")
                if desc:
                    st.write(desc[:800] + ("..." if len(desc)>800 else ""))
                st.markdown("---")
                c1,c2,c3 = st.columns(3)
                c1.metric("52?梢?暺?, fmt(info.get("fiftyTwoWeekHigh"),".2f"))
                c2.metric("52?曹?暺?, fmt(info.get("fiftyTwoWeekLow"),".2f"))
                c3.metric("Beta",     fmt(info.get("beta"),".2f"))
                dy = info.get("dividendYield")
                c1.metric("?⊥畾??, f"{dy*100:.2f}%" if dy else "??)
                av = info.get("averageVolume")
                c2.metric("??", f"{av/1e6:.1f}M" if av else "??)
                so = info.get("sharesOutstanding")
                c3.metric("瘚??, f"{so/1e9:.2f}B" if so else "??)

    # ??????????????????????????????????????????????????????
    # TAB 2: ?芷?⊥???    # ??????????????????????????????????????????????????????
    with tabs[1]:
        sec("?? ?芷?⊥???)
        gs_list, gs_status = load_gsheets_watchlist()
        if gs_list:
            st.success(gs_status)
            default_wl = "\n".join(gs_list)
        else:
            st.warning(gs_status)
            default_wl = "AAPL\nNVDA\nTSLA\nMSFT\nMETA\n2330.TW\n2317.TW\n2454.TW"

        col_in, col_btn = st.columns([4,1])
        wl_raw  = col_in.text_area("瘥?銝?誨??, default_wl, height=200)
        col_btn.markdown("<br><br><br>", unsafe_allow_html=True)
        run_scan = col_btn.button("?? ????", type="primary", use_container_width=True)

        if run_scan:
            tickers = [t.strip().upper() for t in wl_raw.split("\n") if t.strip()]
            rows = []
            prog = st.progress(0, "??銝?..")
            for i, t in enumerate(tickers):
                try:
                    inf = enrich_info(t, get_info(t)); dfx = get_price(t, "3mo")
                    if dfx.empty: continue
                    tc = tech_signal(dfx); fc = fund_score(inf); pc = peg_model(inf)
                    sg, _ = composite(tc, fc, pc)
                    px = inf.get("currentPrice") or inf.get("regularMarketPrice") or dfx["Close"].iloc[-1]
                    rows.append({"隞?Ⅳ":t,"?迂":(inf.get("shortName","")or"")[:16],
                                 "?曉":f"{px:.2f}","5??":f"{tc.get('ret5',0):+.1f}%",
                                 "?銵?:tc["signal"],"?箸??:f"{fc['score']}/100",
                                 "PEG":f"{pc['peg']:.2f}" if pc.get("peg") else "??,
                                 "隡啣?:pc.get("verdict","??),"RSI":f"{tc['rsi']:.0f}" if tc.get("rsi") else "??,
                                 "蝬?撱箄降":sg})
                except Exception:
                    pass
                prog.progress((i+1)/len(tickers), f"?? {t}...")
            prog.empty()
            if rows:
                wdf = pd.DataFrame(rows)
                def cmap(v):
                    if "撘瑕?鞎琿? in str(v): return "background:#002a1a;color:#00d896"
                    if "?澆??釣" in str(v): return "background:#00200f;color:#4ecf8c"
                    if "撱箄降?輸?" in str(v): return "background:#2a0010;color:#ff4060"
                    if "雓寞?" in str(v):     return "background:#2a1500;color:#ff8c42"
                    return ""
                st.dataframe(wdf.style.map(cmap, subset=["蝬?撱箄降"]),
                             use_container_width=True, height=380)
                st.download_button("漎? 銝? CSV",
                    wdf.to_csv(index=False, encoding="utf-8-sig"),
                    f"scan_{datetime.now():%Y%m%d}.csv", "text/csv")

    # ??????????????????????????????????????????????????????
    # TAB 3: 鞎瑕瘙箇?
    # ??????????????????????????????????????????????????????
    with tabs[2]:
        sec("?? 鞎瑕瘙箇???")
        st.caption("?迄雿隞暻潭?行?銝?佗?隞亙?隞暻潭????舀憟賜??脣??")
        c1,c2,c3,c4 = st.columns(4)
        b_t = c1.text_input("?∠巨隞??","NVDA",key="bt").strip().upper()
        b_p = c2.number_input("?格?鞎瑕?對??詨‵嚗?=?函?對?",0.0,step=0.5,key="bp")
        b_y = c3.selectbox("閮???",["<1撟?,"1-2撟?,"3-5撟?,">5撟?],index=2,key="by")
        b_r = c4.selectbox("憸券?踹?摨?,["雿?(-8%)","銝?(-15%)","擃?(-30%)"],index=1,key="br")

        if st.button("? ??鞎瑕??", type="primary", key="b_go"):
            with st.spinner("??銝?.."):
                bi = enrich_info(b_t, get_info(b_t)); bd = get_price(b_t, "1y")
            tc = tech_signal(bd); fc = fund_score(bi); pc = peg_model(bi)
            curr = bi.get("currentPrice") or bi.get("regularMarketPrice") or (bd["Close"].iloc[-1] if not bd.empty else 0)

            ymap = {"<1撟?:0.5,"1-2撟?:1.5,"3-5撟?:4,">5撟?:7}
            yrs  = ymap.get(b_y, 3)
            is_short = yrs < 2

            score = 0
            pros  = []
            cons  = []

            # --- 1. ?格???vs ?曉 ---
            if b_p and curr and b_p > 0:
                mg = (curr - b_p) / b_p * 100
                if mg <= -5:   score += 20; pros.append(f"?格?鞎瑕?寞??曉雿?{-mg:.1f}%嚗?摰??")
                elif mg <= 0:  score += 10; pros.append(f"?格?鞎瑕?寞餈?對?雿蔭??")
                elif mg <= 5:  score +=  3; cons.append(f"?格?鞎瑕?寞??曉擃?{mg:.1f}%嚗遣霅啁??矽")
                else:          score -= 15; cons.append(f"?格?鞎瑕?寞??曉擃?{mg:.1f}%嚗之撟滯?對?撱箄降?身?格?")

            # --- 2. ?????? ---
            if yrs >= 5:
                score += 15; pros.append("閮??? 5 撟港誑銝????臭??????剜?瘜Ｗ?敶梢敺?")
            elif yrs >= 2:
                score +=  8; pros.append("銝剜???嚗??? 撟湛?嚗?摰?餈質馱?箸?Ｚ???)
            else:
                pros.append("?剜???嚗? 1 撟湛?嚗?銵?舫??蛛?閮?閮剖末??暺?)

            # --- 3. ?箸??---
            fs = fc["score"]
            if is_short:
                if fs >= 60:   score += 10; pros.append(f"?箸??{fs}/100 ?臬末嚗蝺漱????")
                elif fs < 40:  score -=  5; cons.append(f"?箸??{fs}/100 ?摹嚗蝺??渲牲??)
            else:
                if fs >= 70:   score += 25; pros.append(f"?箸??{fs}/100 ?芾嚗????瘞?雲")
                elif fs >= 55: score += 12; pros.append(f"?箸??{fs}/100 銝剔?嚗???閫撖?)
                elif fs >= 40: score -=  5; cons.append(f"?箸??{fs}/100 ?摹嚗?????望")
                else:          score -= 20; cons.append(f"?箸??{fs}/100 撌殷?銝遣霅圈?瘜?)

            # --- 4. ?銵 ---
            ts  = tc["score"]
            rsi = tc.get("rsi")
            if is_short:
                if ts >= 40:   score += 25; pros.append(f"?銵???{ts:+d}嚗蝺脣???臬末")
                elif ts >= 0:  score +=  5; pros.append(f"?銵???{ts:+d}嚗?銵銝剜?)
                elif ts >= -20:score -= 10; cons.append(f"?銵???{ts:+d}嚗蝺?撘梧??航蝜潛?銝")
                else:          score -= 20; cons.append(f"?銵???{ts:+d}嚗蝺?憿臬?蝛綽?撱箄降蝑???憭???)
            else:
                if ts >= 40:   score += 15; pros.append(f"?銵???{ts:+d}嚗?隅?Ｗ?銝?)
                elif ts >= 0:  score +=  5; pros.append(f"?銵???{ts:+d}嚗?銵銝剜改??臬??孵?撅")
                elif ts >= -20:score -=  5; cons.append(f"?銵???{ts:+d}嚗?粥撘梧?雿蝺蝑摨?鞎?)
                else:          score -= 10; cons.append(f"?銵???{ts:+d}嚗隅?Ｗ?蝛綽?撱箄降蝑?敶Ⅱ隤???)

            # --- 5. RSI ---
            if rsi:
                if rsi < 30:   score += 15; pros.append(f"RSI {rsi:.0f} 頞都嚗風?脖??舐撠?暺???璈?擃?)
                elif rsi < 42: score +=  8; pros.append(f"RSI {rsi:.0f} ??嚗???蝛粹?")
                elif rsi > 75: score -= 10; cons.append(f"RSI {rsi:.0f} 頞眺嚗蝺?賢?隤選?銝?雿喳?湧?")
                elif rsi > 65: score -=  5; cons.append(f"RSI {rsi:.0f} ??嚗蕭擃?憸券")

            # --- 6. 隡啣?PEG ---
            pv = pc.get("peg")
            if pv:
                if pv < 0.8:   score += 20; pros.append(f"PEG {pv:.2f}嚗?憿臭?隡堆??鋡怠??游蕭??)
                elif pv < 1.3: score += 12; pros.append(f"PEG {pv:.2f}嚗摯?澆???)
                elif pv < 2.0: score +=  0; cons.append(f"PEG {pv:.2f}嚗摯?澆?擃???蝬剜???敺?")
                else:          score -= 15; cons.append(f"PEG {pv:.2f}嚗摯?潮?擃??閬扔擃??瑞?????)

            score = max(-100, min(100, score))

            # 蝯??瑼餃????矽??            if is_short:
                if score >= 55:  verdict, vc = "???剔??臭誑?脣", "#00d896"
                elif score >= 20: verdict, vc = "??蝑?閮?蝣箄?", "#ffc842"
                else:             verdict, vc = "???剔?銝遣霅圈?, "#ff4060"
            else:
                if score >= 40:  verdict, vc = "??撱箄降鞎琿?, "#00d896"
                elif score >= 10: verdict, vc = "??蝑??游末??", "#ffc842"
                else:             verdict, vc = "???桀?銝遣霅?, "#ff4060"

            st.markdown(
                f'<div class="card" style="border-color:{vc};text-align:center;padding:20px">'
                f'<div style="font-size:28px;font-weight:800;color:{vc}">{verdict}</div>'
                f'<div class="card-sub" style="margin-top:8px">蝬?閰? {score:+d}/100嚚b_y}??蝑</div></div>',
                unsafe_allow_html=True)

            col_pro, col_con = st.columns(2)
            with col_pro:
                sec("???舀?鞎瑕????)
                if pros:
                    for p in pros:
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid #00d896;padding:8px 12px">'
                            f'<span class="green">??/span> {p}</div>', unsafe_allow_html=True)
                else:
                    st.markdown("?桀?瘝??＊?舀?鞎瑕????)
            with col_con:
                sec("???曉鞎琿?閬釣??憸券")
                if cons:
                    for c_item in cons:
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid #ff4060;padding:8px 12px">'
                            f'<span class="red">??/span> {c_item}</div>', unsafe_allow_html=True)
                else:
                    st.markdown("?桀?瘝??＊霅衣內嚗??脣")

            # 隞暻潭???瘥??拙?鞎?            sec("? 隞暻潭???頛?眺嚗?)
            tips = []
            if rsi and rsi > 60:
                target_rsi = 35 if rsi > 72 else 45
                tips.append(f"蝑?RSI ???{target_rsi} 隞乩??莎????湧?")
            if pv and pv > 1.5:
                tips.append(f"蝑?PEG ? 1.3 隞乩?嚗摯?澆?甇詨?????撅")
            if ts < 0 and not bd.empty:
                df_ind = add_indicators(bd)
                ma20 = df_ind["MA20"].iloc[-1] if not pd.isna(df_ind["MA20"].iloc[-1]) else None
                ma60 = df_ind["MA60"].iloc[-1] if not pd.isna(df_ind["MA60"].iloc[-1]) else None
                if ma20 and curr < ma20:
                    tips.append(f"蝑?寧???MA20嚗? ${ma20:.2f}嚗Ⅱ隤蝺隅?Ｚ?憭?)
                if ma60 and curr < ma60:
                    tips.append(f"蝑?寧???MA60嚗? ${ma60:.2f}嚗Ⅱ隤葉?隅?Ｚ?憭?)
                tips.append("蝑?MACD ?箇??嚗ACD 蝺銝?銝忽頞???嚗??脣")
            if not bd.empty:
                support = bd.tail(20)["Low"].min()
                if curr and curr > support * 1.06:
                    tips.append(f"?亥?孵?皜祆?? ${support:.2f} ??嚗?20?乩?暺?嚗??鞎瑕")
            if not is_short and fs < 50:
                tips.append("蝑?摮?瓷?梁Ⅱ隤?祇?臬?孵?嚗?瘙箏??臬?")
            if not tips:
                if score >= 40:
                    tips.append("?桀????迤?ｇ??臭??芸楛???祉璅??寥脣嚗?敹?敺?)
                else:
                    tips.append("?桀?憭????摹嚗遣霅啗???4?? ?勗??閰摯")
            for tip in tips:
                st.markdown(f"??{tip}")

            # 餈?韏啣?孵?
            sec("?? 餈?韏啣?孵?")
            if not bd.empty and len(bd) >= 20:
                avg5  = bd["Close"].iloc[-5:].mean()
                avg20 = bd["Close"].iloc[-20:].mean()
                trend_dir = "銝?" if avg5 > avg20 else "銝?"
                tc2 = "#00d896" if trend_dir == "銝?" else "#ff4060"
                ret5  = tc.get("ret5", 0)
                ret20 = tc.get("ret20", 0)
                st.markdown(
                    f"?剜??? vs 銝剜???嚗隅??<span style='color:{tc2}'><b>{trend_dir}銝?/b></span>嚗?
                    f"5?交撞頝?**{ret5:+.1f}%**嚗?0?交撞頝?**{ret20:+.1f}%**",
                    unsafe_allow_html=True)

            if not bd.empty:
                st.plotly_chart(price_chart(bd, b_t), use_container_width=True)

    # ??????????????????????????????????????????????????????
    # TAB 4: 鞈?瘙箇?
    # ??????????????????????????????????????????????????????
    with tabs[3]:
        sec("?? 鞈?瘙箇???")
        st.caption("頛詨??閮??斗??隢??臬隞?蝡?蝯血靽?/撟唾﹛/蝛扔銝車鞈??")
        s1,s2,s3 = st.columns(3)
        s_t = s1.text_input("???∠巨","AAPL",key="st").strip().upper()
        s_c = s2.number_input("???$)",0.0,step=0.5,key="sc")
        s_q = s3.number_input("???⊥",0,step=1,key="sq")

        if st.button("?? ????, type="primary", key="s_go"):
            with st.spinner("??銝?.."):
                si = get_info(s_t); sd = get_price(s_t,"1y")
            curr = si.get("currentPrice") or si.get("regularMarketPrice") or (sd["Close"].iloc[-1] if not sd.empty else 0)
            gp = (curr - s_c) / s_c * 100 if s_c else 0
            ga = (curr - s_c) * s_q if s_c and s_q else 0
            sc = tech_signal(sd); sf = fund_score(si); sp = peg_model(si)
            fv = sp.get("fair_value")

            gc = "#00d896" if gp>=0 else "#ff4060"
            st.markdown(
                f'<div class="card"><div style="display:flex;justify-content:space-between">'
                f'<div><div class="card-label">????/div>'
                f'<div style="color:{gc};font-size:28px;font-weight:800">{gp:+.1f}%</div></div>'
                f'<div style="text-align:right"><div class="card-label">撣潭???/div>'
                f'<div style="color:{gc};font-size:24px;font-weight:700">{"${:,.0f}".format(ga) if ga else "??}</div></div>'
                f'</div></div>', unsafe_allow_html=True)

            sec("銝車鞈??")
            strats = [
                ("?儭?靽?",
                 "鞈? 50% ?其?" if gp>20 or sc["score"]<-20 else f"閮剖???{s_c*0.92:.2f}嚗???{s_c*1.25:.2f}",
                 "?質??箏?嚗?????撖?),
                ("?? 撟唾﹛",
                 "皜Ⅳ 30%" if (fv and curr>fv*1.2) else "蝜潛???嚗蕭頩文迤??,
                 f"?曉{'擃' if fv and curr>fv*1.2 else '?亥?'}??隡啣?{fv:.2f}" if fv else "?箸?Ｘ?箇?渲?閮?"),
                ("?? 蝛扔",
                 "?冽????Ⅳ" if sf["score"]>=70 and gp<50 else "鞈? 80%嚗? 20% ?蝺?,
                 f"?箸?┐sf['score']}/100嚗'??摩摰' if sf['score']>=70 else '撌脣之撟??}"),
            ]
            for icon_type, action, reason in strats:
                st.markdown(
                    f'<div class="card">'
                    f'<div style="color:#6b7a99;font-weight:600">{icon_type}</div>'
                    f'<div style="color:#f0f2f5;font-size:16px;font-weight:700;margin:4px 0">{action}</div>'
                    f'<div style="color:#9b8cff;font-size:13px">{reason}</div>'
                    f'</div>', unsafe_allow_html=True)

    # ??????????????????????????????????????????????????????
    # TAB 5: ?∠巨瘥?
    # ??????????????????????????????????????????????????????
    with tabs[4]:
        sec("?? 憭瘥?嚗?憭?4 ?荔?")
        cc = st.columns(4)
        defaults = ["AAPL","MSFT","GOOGL","META"]
        cmp_tks = [c.text_input(f"?∠巨 {i+1}", d, key=f"cmp{i}").strip().upper()
                   for i,( c,d) in enumerate(zip(cc, defaults))]

        if st.button("?? ??瘥?", type="primary", key="cmp_go"):
            cdata = []
            with st.spinner("頛..."):
                for tkr in [t for t in cmp_tks if t]:
                    inf = get_info(tkr); dfx = get_price(tkr,"1y")
                    if dfx.empty: continue
                    tc = tech_signal(dfx); fc = fund_score(inf); pc = peg_model(inf)
                    sg, _ = composite(tc, fc, pc)
                    px = inf.get("currentPrice") or inf.get("regularMarketPrice") or dfx["Close"].iloc[-1]
                    cdata.append({"隞?Ⅳ":tkr,"?迂":(inf.get("shortName","")or"")[:14],
                                  "?曉":px,
                                  "ROE%":inf.get("returnOnEquity",None) and inf["returnOnEquity"]*100,
                                  "瘥??":inf.get("grossMargins",None) and inf["grossMargins"]*100,
                                  "??%":inf.get("revenueGrowth",None) and inf["revenueGrowth"]*100,
                                  "瘛典??":inf.get("profitMargins",None) and inf["profitMargins"]*100,
                                  "P/E":inf.get("trailingPE"),"PEG":pc.get("peg"),
                                  "Beta":inf.get("beta"),"?箸??:fc["score"],"?銵?:tc["score"],
                                  "撱箄降":sg,"df":dfx})

            if cdata:
                st.plotly_chart(comparison_chart([(d["隞?Ⅳ"],d["df"]) for d in cdata]),
                                use_container_width=True)
                show_cols = ["隞?Ⅳ","?迂","?曉","ROE%","瘥??","??%","瘛典??","P/E","PEG","Beta","?箸??,"?銵?,"撱箄降"]
                cdf = pd.DataFrame([{k:v for k,v in d.items() if k!="df"} for d in cdata])[show_cols]
                for nc in ["ROE%","瘥??","??%","瘛典??","P/E","PEG","Beta","?箸??,"?銵?]:
                    cdf[nc] = pd.to_numeric(cdf[nc],errors="coerce").round(1)
                st.dataframe(cdf.style.highlight_max(
                    subset=["ROE%","瘥??","??%","瘛典??","?箸??,"?銵?], color="#002a1a"
                ).highlight_min(subset=["PEG","P/E","Beta"], color="#002a1a"),
                use_container_width=True)

                sec("蝬???")
                ranked = sorted(cdata, key=lambda x: x["?箸??]*0.6+x["?銵?]*0.4, reverse=True)
                for i, d in enumerate(ranked):
                    medal = ["??","??","??","4儭"][i]
                    st.markdown(f"{medal} **{d['隞?Ⅳ']}** {d['?迂']} ???箸??{d['?箸??]}/100 | {d['撱箄降']}")

    # ??????????????????????????????????????????????????????
    # TAB 6: 憸券?
    # ??????????????????????????????????????????????????????
    with tabs[5]:
        sec("? 鞎瑕?憸券?")
        r_t = st.text_input("?∠巨隞??","TSLA",key="rt").strip().upper()
        if st.button("?? ??憸券", type="primary", key="r_go"):
            with st.spinner("??銝?.."):
                ri = get_info(r_t); rd = get_price(r_t,"1y")
                risks = risk_scan(ri, rd)
            hi = [x for x in risks if x[1]=="h"]
            mi = [x for x in risks if x[1]=="m"]
            lo = [x for x in risks if x[1]=="l"]
            c1,c2,c3 = st.columns(3)
            c1.metric("擃◢??,"? "+str(len(hi))+" ?? if hi else "????)
            c2.metric("銝剝◢??,"?? "+str(len(mi))+" ?? if mi else "????)
            c3.metric("雿??⊿◢??,"? "+str(len(lo))+" ??)
            for group, title, border in [
                (hi,"? 擃◢??,"#ff4060"),(mi,"?? 銝剝◢??,"#ff8c42"),(lo,"? 雿◢??,"#00d896")
            ]:
                if group:
                    sec(title)
                    for lbl, _, desc in group:
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid {border}">'
                            f'<div style="color:#f0f2f5;font-weight:600">{lbl}</div>'
                            f'<div style="color:#6b7a99;font-size:13px;margin-top:3px">? {desc}</div></div>',
                            unsafe_allow_html=True)

    # ??????????????????????????????????????????????????????
    # TAB 7: ??蝯?
    # ??????????????????????????????????????????????????????
    with tabs[6]:
        sec("? ??蝯??蔭撱箄降")
        budget   = st.number_input("?舀?鞈???$)",1000,step=500,value=10000,key="pf_b")
        pf_raw   = st.text_area("??∠巨嚗?銵???","AAPL\nMSFT\nNVDA\n2330.TW",key="pf_t")
        pf_risk  = st.radio("憸券?末",["??芸?","?﹛","?脩戌靽?"],horizontal=True,key="pf_r")

        if st.button("? 閮??蔭", type="primary", key="pf_go"):
            pf_tks = [t.strip().upper() for t in pf_raw.split("\n") if t.strip()]
            scores = []
            with st.spinner("閮?銝?.."):
                for t in pf_tks:
                    inf = get_info(t); dfx = get_price(t,"6mo")
                    fc = fund_score(inf); tc = tech_signal(dfx)
                    scores.append({"ticker":t,"name":(inf.get("shortName","")or t)[:14],
                                   "fs":fc["score"],"ts":tc["score"],"beta":inf.get("beta",1) or 1})
            wfn = {
                "??芸?": lambda x: x["fs"]*0.5 + x["ts"]*0.5,
                "?﹛":     lambda x: x["fs"]*0.7 + x["ts"]*0.3,
                "?脩戌靽?": lambda x: x["fs"]*0.9 - (x["beta"]-1)*10,
            }[pf_risk]
            for s in scores: s["w"] = max(0, wfn(s))
            tw = sum(s["w"] for s in scores) or 1
            cash_p = {"??芸?":5,"?﹛":10,"?脩戌靽?":20}[pf_risk]
            inv_p  = 100 - cash_p
            rows = []
            for s in scores:
                ap = s["w"]/tw*inv_p
                rows.append({"隞?Ⅳ":s["ticker"],"?迂":s["name"],"?箸??:s["fs"],
                             "?銵?:s["ts"],"?蔭瘥?":f"{ap:.1f}%","撱箄降??":f"${budget*ap/100:,.0f}"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.success(f"? 撱箄降靽??暸?嚗cash_p}% = ${budget*cash_p/100:,.0f}")

    # ??????????????????????????????????????????????????????
    # TAB 8: 鞎∪閫??
    # ??????????????????????????????????????????????????????
    with tabs[7]:
        sec("?? 鞎∪敹恍圾霈")
        e_t = st.text_input("?∠巨隞??","AAPL",key="et").strip().upper()
        if st.button("?? 閫??鞎∪", type="primary", key="e_go"):
            with st.spinner("頛鞎∪..."):
                ei = get_info(e_t); ef = get_financials(e_t)
            sec("?祆???詨?")
            rev = ei.get("totalRevenue"); rg = ei.get("revenueGrowth")
            eps = ei.get("trailingEps");  pm = ei.get("profitMargins")
            gm  = ei.get("grossMargins"); tpe = ei.get("trailingPE"); fpe = ei.get("forwardPE")
            eg  = ei.get("earningsGrowth")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("撟游??嗅", f"${rev/1e9:.1f}B" if rev else "??, f"{rg*100:+.1f}% YoY" if rg else "")
            c2.metric("EPS (TTM)", f"${eps:.2f}" if eps else "??)
            c3.metric("瘛典??, f"{pm*100:.1f}%" if pm else "??)
            c4.metric("瘥??, f"{gm*100:.1f}%" if gm else "??)
            sec("???")
            c1,c2,c3 = st.columns(3)
            c1.metric("?嗅? P/E",   f"{tpe:.1f}x" if tpe else "??)
            c2.metric("?? P/E",   f"{fpe:.1f}x" if fpe else "??)
            c3.metric("????摯", f"{eg*100:+.1f}%" if eg else "??)
            sec("鞎∪閰摯")
            if rg and rg>0.15:  st.markdown("???撘瑕??")
            elif rg and rg<0:    st.markdown("???銵圈嚗?霅行?")
            if pm and pm>0.15:   st.markdown("??瘛典?摨?)
            if fpe and tpe and fpe<tpe: st.markdown("????隡啣澆?潛??撣???")
            if ef.get("earnings") is not None:
                try:
                    edf = pd.DataFrame(ef["earnings"])
                    if not edf.empty:
                        sec("甇瑕 EPS"); st.dataframe(edf.tail(8), use_container_width=True)
                except Exception:
                    pass

    # ??????????????????????????????????????????????????????
    # TAB 9: ?瑟???
    # ??????????????????????????????????????????????????????
    with tabs[8]:
        sec("???瑟?????")
        lt_t = st.text_input("?∠巨隞??","MSFT",key="ltt").strip().upper()
        lt_y = st.selectbox("閮???",["5撟?,"10撟?,"15撟?],key="lty")

        if st.button("? ???瑟??孵?, type="primary", key="lt_go"):
            with st.spinner("??銝?.."):
                li = get_info(lt_t); ld = get_price(lt_t,"5y")
                lf = fund_score(li); lp = peg_model(li)
            sec("霅瑕?瘝唾?隡?)
            gm = li.get("grossMargins",0) or 0; roe = li.get("returnOnEquity",0) or 0
            if gm>0.5:  st.markdown("??**擃??拍? >50%** ??摰?賢?撘瘀????祈風?眾")
            if roe>0.2:  st.markdown("??**擃?ROE >20%** ??鞈??擃?蝡嗥?芸?＊")
            mc = li.get("marketCap",0) or 0
            if mc>100e9: st.markdown("??**憭批??潮???* ??閬芋??撘瘀?撣隞賡?蝛拙")
            de = li.get("debtToEquity")
            if de and de<50: st.markdown("??**雿???* ??鞎∪?蝛拙嚗?憸券?賢?撘?)

            sec("?瑟??梢隡啁?")
            cp = li.get("currentPrice") or li.get("regularMarketPrice")
            eg = li.get("earningsGrowth") or li.get("revenueGrowth") or 0.10
            yrs = int(lt_y.replace("撟?,""))
            if cp and eg>0:
                c1,c2,c3 = st.columns(3)
                bull = cp*(1+eg*1.2)**yrs; base = cp*(1+eg*0.8)**yrs; bear = cp*(1+max(eg-0.05,0.02))**yrs
                c1.metric("璅?",f"${bull:.0f}",f"+{(bull/cp-1)*100:.0f}%")
                c2.metric("?箸",f"${base:.0f}",f"+{(base/cp-1)*100:.0f}%")
                c3.metric("?脰?",f"${bear:.0f}",f"+{(bear/cp-1)*100:.0f}%")
            sec("隢??渲?靽∟?")
            st.markdown("""
- ? ??? 2 摮?ROE 雿 10%
- ? 瘥???銝?頞? 5 ???
- ? ?詨?璆剖?鋡恍?閬扳?銵隞?- ? 蝞∠?撅斤??CEO/CFO ?湔?嚗?- ? ?芰?暸?瘚?? 3 摮??皛?- ? 鞎瘥???150%
            """)

    # ??????????????????????????????????????????????????????
    # TAB 10: 銝駁?皜
    # ??????????????????????????????????????????????????????
    with tabs[9]:
        sec("?? 銝駁??∠巨皜")
        THEMES = {
            "?? AI / ??擃?: ["NVDA","AMD","AVGO","AMAT","ASML","2330.TW","2454.TW"],
            "?? 蝘? / ?脩垢":  ["MSFT","GOOGL","AMZN","META","CRM","SNOW"],
            "? ?怎???":     ["JNJ","UNH","ABBV","LLY","MRNA","PFE"],
            "??皜??賣?":     ["ENPH","FSLR","NEE","PLUG","BEP"],
            "? 擃??:       ["KO","PG","JNJ","VZ","T","MO","XOM"],
            "? ??蝘?":     ["V","MA","PYPL","SQ","NU"],
            "?? 瘨祥?嗅":     ["AMZN","WMT","COST","TGT","SBUX"],
            "?? ?啗蝎暸":     ["2330.TW","2317.TW","2454.TW","3008.TW","2382.TW"],
        }
        th_sel = st.selectbox("?豢?銝駁?", list(THEMES.keys()), key="th_sel")
        if st.button("?? ??甇支蜓憿?, type="primary", key="th_go"):
            rows = []; prog = st.progress(0); tks = THEMES[th_sel]
            for i, t in enumerate(tks):
                try:
                    inf = get_info(t); dfx = get_price(t,"3mo")
                    if dfx.empty: continue
                    tc = tech_signal(dfx); fc = fund_score(inf); pc = peg_model(inf)
                    sg,_ = composite(tc,fc,pc)
                    px = inf.get("currentPrice") or inf.get("regularMarketPrice") or dfx["Close"].iloc[-1]
                    rows.append({"隞?Ⅳ":t,"?砍":(inf.get("shortName","")or"")[:16],
                                 "?曉":f"{px:.2f}","?Ｘ平":(inf.get("industry","")or"")[:20],
                                 "?箸??:f"{fc['score']}/100","?銵?:tc["signal"],
                                 "PEG":f"{pc['peg']:.2f}" if pc.get("peg") else "??,
                                 "5??":f"{tc.get('ret5',0):+.1f}%","撱箄降":sg})
                except Exception:
                    pass
                prog.progress((i+1)/len(tks))
            prog.empty()
            if rows:
                thdf = pd.DataFrame(rows)
                def cmap2(v):
                    if "撘瑕?鞎琿? in str(v): return "background:#002a1a;color:#00d896"
                    if "?澆??釣" in str(v): return "background:#00200f;color:#4ecf8c"
                    if "撱箄降?輸?" in str(v): return "background:#2a0010;color:#ff4060"
                    return ""
                st.dataframe(thdf.style.map(cmap2,subset=["撱箄降"]),
                             use_container_width=True, height=400)

    # ??????????????????????????????????????????????????????
    # TAB 11: 隞鞎∠??啗?
    # ??????????????????????????????????????????????????????
    with tabs[10]:
        sec("? 隞鞎∠??啗?")
        st.caption("?芸?敶蝢憭抒??～??⊥??啣???瘥?30 ???湔銝甈?)

        col_filter, col_refresh = st.columns([4,1])
        news_lang = col_filter.radio("蝭拚",["?券","蝢?賊?","?啗?賊?"],
                                     horizontal=True, key="news_filter")
        if col_refresh.button("?? 蝡?湔", key="news_refresh"):
            st.cache_data.clear()

        with st.spinner("頛?啗?..."):
            all_news = get_market_news()

        tw_sources = {"^TWII","2330.TW","2317.TW","2454.TW","2308.TW",
                      "2412.TW","2303.TW","3711.TW","0050.TW","2882.TW",
                      "2881.TW","2886.TW","1301.TW","2002.TW","3008.TW"}
        us_sources = {"^GSPC","^IXIC","NVDA","AAPL","META","TSLA","MSFT","AMD","GOOGL","AMZN"}

        if news_lang == "?啗?賊?":
            filtered = [n for n in all_news if n.get("_src") in tw_sources]
        elif news_lang == "蝢?賊?":
            filtered = [n for n in all_news if n.get("_src") in us_sources]
        else:
            filtered = all_news

        st.caption(f"?勗?敺?{len(all_news)} ???蝭拚敺?{len(filtered)} ??)

        # AI 銝剜???嚗?閬?GEMINI_API_KEY嚗?        try:
            has_gemini = bool(st.secrets["GEMINI_API_KEY"])
        except Exception:
            has_gemini = False

        if filtered:
            sec("?? AI 隞撣??")
            if not has_gemini:
                st.caption("撠閮剖? GEMINI_API_KEY嚗???Streamlit Cloud ??Settings ??Secrets ?啣?")
            else:
                headlines_text = "\n".join(
                    f"[{'?啗' if n.get('_src','') in tw_sources else '蝢'}] {n['title']}"
                    for n in filtered[:25]
                )
                with st.spinner("AI ??銝?.."):
                    summary = gemini_news_summary(headlines_text)
                if summary:
                    st.markdown(
                        f'<div class="card" style="border-color:#9b8cff;padding:16px 20px;line-height:1.8">'
                        f'{summary.replace(chr(10), "<br>")}</div>',
                        unsafe_allow_html=True)
            st.markdown("---")

        if not filtered:
            st.info("?急?瘝??啗?嚗?蝔??岫")
        else:
            src_label = {
                "^GSPC":"S&P500","^IXIC":"NASDAQ","^TWII":"?啁??",
                "NVDA":"NVDA","AAPL":"AAPL","META":"META","TSLA":"TSLA",
                "MSFT":"MSFT","AMD":"AMD","GOOGL":"Google","AMZN":"Amazon",
                "2330.TW":"?啁???,"2317.TW":"暾餅絲","2454.TW":"?舐蝘?,
                "2308.TW":"?圈???,"2412.TW":"銝剛??,"2303.TW":"?舫",
                "3711.TW":"?交???,"0050.TW":"?之?啁50","2882.TW":"?陸??,
                "2881.TW":"撖??,"2886.TW":"????,"1301.TW":"?啣?",
                "2002.TW":"銝剝","3008.TW":"憭抒???,
            }
            for item in filtered:
                title = item.get("title","")
                link  = item.get("link","#")
                pub   = item.get("publisher","")
                ts    = item.get("providerPublishTime",0)
                src   = item.get("_src","")
                dt    = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M") if ts else ""
                tag   = src_label.get(src, src)
                tag_color = "#9b8cff" if src in tw_sources else "#00d896"

                st.markdown(
                    f'<div class="news-item">'
                    f'<div><a href="{link}" target="_blank">{title}</a></div>'
                    f'<div class="news-meta">'
                    f'<span style="background:#1a2035;color:{tag_color};padding:1px 7px;'
                    f'border-radius:4px;font-size:11px;margin-right:6px">{tag}</span>'
                    f'{pub} 繚 {dt}</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    st.caption("?? ?砍極?瑕?靘?蝛嗉???桃?嚗?瑽?隞颱???撱箄降??鞈?憸券嚗?撖拇?閰摯??)


if __name__ == "__main__":
    main()
