# ============================================================
#  AI 選股工作站 v2 — 零成本版
#  數據：yfinance | 資料庫：Google Sheets | 部署：Streamlit Cloud
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

# ── Page config (MUST be first) ─────────────────────────────
st.set_page_config(
    page_title="📈 選股工作站",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Dark Mode CSS ────────────────────────────────────────────
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


# ════════════════════════════════════════════════════════════
#  DATA FETCHING  (cached)
# ════════════════════════════════════════════════════════════

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


# ── Method A：從 yfinance 季報表自己算 ──────────────────────

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
            # Revenue YoY（同季比）
            if len(rev) >= 5:
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

            # 負債比
            debt = find(bal, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
            eq2  = find(bal, ["Stockholders Equity", "Total Stockholder Equity", "Common Stock Equity"])
            if debt is not None and eq2 is not None:
                d0 = float(debt.iloc[0]) if not pd.isna(debt.iloc[0]) else None
                e0 = float(eq2.iloc[0]) if not pd.isna(eq2.iloc[0]) else None
                if d0 is not None and e0 and e0 != 0:
                    result["debtToEquity"] = (d0 / e0) * 100

    except Exception:
        pass
    return result


# ── Method B：FinMind API 補台股財報 ─────────────────────────

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
                result["returnOnEquity"] = roe / 100  # FinMind 回傳 % 數字

            # 營收 YoY
            rev_df = df[df["type"] == "Revenue"].head(6)
            if len(rev_df) >= 5:
                r0 = float(rev_df.iloc[0]["value"])
                r4 = float(rev_df.iloc[4]["value"])
                if r4 and r4 != 0:
                    result["revenueGrowth"] = (r0 - r4) / abs(r4)

    except Exception:
        pass
    return result


# ── 合併所有來源 ──────────────────────────────────────────────

def enrich_info(ticker: str, base_info: dict) -> dict:
    """用 A + B 填補 yfinance info 的空白欄位"""
    info = dict(base_info)

    # Method A（所有股票都跑）
    for key, val in calc_from_statements(ticker).items():
        if info.get(key) is None and val is not None:
            info[key] = val

    # Method B（只對台股）
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
    pairs = [("^GSPC","S&P 500"),("^IXIC","NASDAQ"),("^DJI","道瓊"),("^TWII","台灣加權"),("^HSI","恆生")]
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
    """回傳 (ticker列表, 狀態訊息)"""
    # Step 1: 讀取 URL
    try:
        url = st.secrets["GSHEET_CSV_URL"]
    except Exception:
        return [], "❌ Streamlit Secrets 裡找不到 GSHEET_CSV_URL，請確認有存檔"

    if not url or not url.startswith("http"):
        return [], "❌ GSHEET_CSV_URL 網址格式不正確"

    # Step 2: 讀取 CSV
    try:
        df = pd.read_csv(url)
    except Exception as e:
        return [], f"❌ 無法讀取 Google Sheet CSV：{str(e)[:80]}"

    # Step 3: 找欄位
    cols = list(df.columns)
    # 找 Stock_ID（不分大小寫）
    col_match = next((c for c in cols if c.strip().upper() == "STOCK_ID"), None)
    if not col_match:
        return [], f"❌ 找不到 Stock_ID 欄位，試算表現有欄位是：{cols}"

    tickers = [t.strip().upper() for t in df[col_match].dropna().tolist() if str(t).strip()]
    if not tickers:
        return [], "⚠️ Stock_ID 欄位是空的，請在 Google Sheet 填入股票代號"

    return tickers, f"✅ 成功從 Google Sheets 讀取 {len(tickers)} 檔"


# ════════════════════════════════════════════════════════════
#  QUANT ENGINE
# ════════════════════════════════════════════════════════════

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
            score += 30; det.append(("黄金交叉 MA5↑MA20", "green"))
        elif pm5 > pm20 and ma5 < ma20:
            score -= 30; det.append(("死亡交叉 MA5↓MA20", "red"))
        if price > ma20: score += 15; det.append(("站上月線 MA20", "green"))
        else:            score -= 15; det.append(("跌破月線 MA20", "red"))
        if ma5 > ma20:   score += 10; det.append(("均線多頭排列", "green"))
        else:            score -= 8;  det.append(("均線空頭排列", "red"))

    ma60 = cur.get("MA60")
    if ma60 and not pd.isna(ma60):
        if price > ma60: score += 10; det.append(("站上季線 MA60", "green"))
        else:            score -= 10; det.append(("跌破季線 MA60", "red"))

    rsi = cur.get("RSI")
    if rsi and not pd.isna(rsi):
        if rsi < 30:    score += 20; det.append((f"RSI 超賣 {rsi:.0f}", "green"))
        elif rsi > 70:  score -= 20; det.append((f"RSI 超買 {rsi:.0f}", "red"))
        else:           det.append((f"RSI 健康 {rsi:.0f}", "yellow"))

    macd = cur.get("MACD"); msig = cur.get("MACD_signal")
    pmacd = prv.get("MACD"); pmsig = prv.get("MACD_signal")
    if all(v is not None and not pd.isna(v) for v in [macd, msig, pmacd, pmsig]):
        if pmacd < pmsig and macd > msig: score += 20; det.append(("MACD 金叉", "green"))
        elif pmacd > pmsig and macd < msig: score -= 20; det.append(("MACD 死叉", "red"))
        if macd > 0: score += 5

    avg_vol = df["Volume"].rolling(20).mean().iloc[-1]
    if cur["Volume"] > avg_vol * 1.5:
        if price > prv["Close"]: score += 10; det.append(("量能放大上漲", "green"))
        else:                    score -= 10; det.append(("量能放大下跌", "red"))

    bb_u = cur.get("BB_upper"); bb_l = cur.get("BB_lower")
    if bb_u and bb_l and not pd.isna(bb_u):
        bb_pct = (price - bb_l) / (bb_u - bb_l) * 100
        if bb_pct < 15:   score += 12; det.append(("觸及布林下軌支撐", "green"))
        elif bb_pct > 85: score -= 12; det.append(("觸及布林上軌壓力", "red"))

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
        det.append((f"{name} {v:.1f}{labels}", "red", "偏低"))

    check("returnOnEquity", 100, [(20,25,"green","優秀≥20%"),(15,18,"green","良好≥15%"),(8,8,"yellow","普通8-15%")], "%", "ROE")
    check("grossMargins",   100, [(50,20,"green","護城河≥50%"),(30,12,"green","良好≥30%"),(15,5,"yellow","普通")], "%", "毛利率")
    check("revenueGrowth",  100, [(25,25,"green","高成長≥25%"),(10,15,"green","穩健≥10%"),(0,5,"yellow","緩成長")], "%", "營收年增")
    check("profitMargins",  100, [(20,15,"green","高利潤≥20%"),(8,8,"yellow","普通")], "%", "淨利率")

    de = info.get("debtToEquity")
    if de is not None:
        if de < 30:    score += 15; det.append((f"負債比 {de:.0f}%", "green", "財務穩健"))
        elif de < 100: score += 5;  det.append((f"負債比 {de:.0f}%", "yellow", "適中"))
        else:          score -= 10; det.append((f"負債比 {de:.0f}%", "red", "高槓桿"))

    cr = info.get("currentRatio")
    if cr:
        if cr >= 2:   score += 10; det.append((f"流動比 {cr:.1f}", "green", "流動性佳"))
        elif cr >= 1: score += 5;  det.append((f"流動比 {cr:.1f}", "yellow", "尚可"))
        else:         score -= 10; det.append((f"流動比 {cr:.1f}", "red", "流動性差"))

    return {"score": max(0, min(100, score)), "details": det}


def peg_model(info: dict) -> dict:
    r = {"peg": None, "fair_value": None, "verdict": "資料不足",
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
            if p < 0.5:   r["verdict"] = "嚴重低估 🟢"
            elif p < 0.8: r["verdict"] = "低估 🟢"
            elif p < 1.2: r["verdict"] = "合理 🟡"
            elif p < 2.0: r["verdict"] = "偏貴 🟠"
            else:          r["verdict"] = "高估 🔴"
    except Exception:
        pass
    return r


def risk_scan(info: dict, df: pd.DataFrame) -> list:
    risks = []
    pe = info.get("trailingPE")
    if pe:
        if pe > 50:   risks.append(("本益比 {:.0f}x 極高".format(pe), "h", "獲利若下滑，股價跌幅很大"))
        elif pe > 30: risks.append(("本益比 {:.0f}x 偏高".format(pe), "m", "估值已反映多數好消息"))
    de = info.get("debtToEquity")
    if de:
        if de > 150: risks.append(("負債比 {:.0f}% 偏高".format(de), "h", "升息環境財務壓力大"))
        elif de > 80: risks.append(("負債比 {:.0f}% 中等".format(de), "m", "需持續觀察"))
    rg = info.get("revenueGrowth")
    if rg and rg < -0.05: risks.append(("營收衰退 {:.1f}%".format(rg*100), "h", "基本面惡化訊號"))
    si = info.get("shortPercentOfFloat")
    if si:
        if si > 0.15: risks.append(("空頭佔流通股 {:.1f}%".format(si*100), "h", "大量做空籌碼"))
        elif si > 0.08: risks.append(("空頭佔流通股 {:.1f}%".format(si*100), "m", "一定做空壓力"))
    beta = info.get("beta")
    if beta:
        if beta > 2:   risks.append((f"Beta {beta:.2f} 高波動", "h", "漲跌是大盤兩倍以上"))
        elif beta > 1.5: risks.append((f"Beta {beta:.2f} 中高波動", "m", "比大盤更震盪"))
    h52 = info.get("fiftyTwoWeekHigh"); l52 = info.get("fiftyTwoWeekLow")
    curr = info.get("currentPrice") or info.get("regularMarketPrice")
    if h52 and l52 and curr and (h52 - l52) > 0:
        pos = (curr - l52) / (h52 - l52) * 100
        if pos > 90: risks.append(("接近52週高點 {:.0f}%".format(pos), "m", "短線上方阻力大"))
    if not df.empty and len(df) >= 60:
        df_i = add_indicators(df)
        ma60 = df_i["MA60"].iloc[-1]
        p    = df_i["Close"].iloc[-1]
        if not pd.isna(ma60) and p < ma60:
            risks.append(("股價跌破季線 MA60", "m", "中期趨勢走弱"))
    if not risks:
        risks.append(("未發現重大警示", "l", "仍需持續追蹤基本面"))
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
    if total >= 65:   return "強力買進 🚀", "#00d896"
    elif total >= 45: return "值得關注 👀", "#4ecf8c"
    elif total >= 25: return "觀望 ⏳", "#ffc842"
    elif total >= 5:  return "謹慎 ⚠️", "#ff8c42"
    else:              return "建議避開 🔴", "#ff4060"


# ════════════════════════════════════════════════════════════
#  PLAIN LANGUAGE ANALYSIS  (新手白話文)
# ════════════════════════════════════════════════════════════

def plain_analysis(ticker: str, info: dict, tech: dict, fund: dict, peg: dict) -> dict:
    name     = info.get("shortName", ticker)
    sector   = info.get("sector", "") or ""
    industry = info.get("industry", "") or ""
    mc       = info.get("marketCap", 0) or 0
    mc_str   = f"${mc/1e9:.0f}B 的大型公司" if mc > 10e9 else f"${mc/1e9:.1f}B 的中型公司" if mc > 1e9 else "小型公司"

    roe   = (info.get("returnOnEquity") or 0) * 100
    gm    = (info.get("grossMargins") or 0) * 100
    rev_g = (info.get("revenueGrowth") or 0) * 100
    de    = info.get("debtToEquity") or 0
    beta  = info.get("beta") or 1
    pv    = peg.get("peg")
    ts    = tech["score"]
    fs    = fund["score"]

    # ── 公司一句話介紹 ──────────────────────────────────────
    sector_zh = {
        "Technology":"科技","Healthcare":"醫療","Financial Services":"金融",
        "Consumer Cyclical":"消費","Industrials":"工業","Energy":"能源",
        "Communication Services":"通訊","Utilities":"公用事業",
        "Basic Materials":"原物料","Real Estate":"房地產",
    }.get(sector, sector)
    intro = f"{name} 是一家 {mc_str}，屬於 {sector_zh or sector} 產業的 {industry or '公司'}。"

    # ── 看漲角度 ────────────────────────────────────────────
    bull = []
    if rev_g > 20:   bull.append(f"📈 營收年增 {rev_g:.0f}%，業績火熱，代表越來越多人買它的產品")
    elif rev_g > 5:  bull.append(f"📈 營收年增 {rev_g:.0f}%，穩定成長中")
    if roe > 20:     bull.append(f"💪 ROE {roe:.0f}%：公司很會用錢賺錢，效率高")
    elif roe > 15:   bull.append(f"💪 ROE {roe:.0f}%：獲利能力不錯")
    if gm > 50:      bull.append(f"🏰 毛利率 {gm:.0f}%：護城河很深，別人很難搶走它的生意")
    elif gm > 30:    bull.append(f"✅ 毛利率 {gm:.0f}%：有一定的定價能力")
    if ts >= 30:     bull.append("📊 技術面向上，短期股價走勢偏強，市場信心足")
    if pv and pv < 1: bull.append(f"💰 PEG {pv:.1f}，比成長速度來說股價還算便宜")
    if de < 30:       bull.append(f"🛡️ 負債比 {de:.0f}%，財務很穩，不容易因借太多錢而出問題")
    if not bull:      bull.append("目前正面訊號不明顯，建議觀察下一季財報")

    # ── 看跌角度 ────────────────────────────────────────────
    bear = []
    if rev_g < 0:    bear.append(f"⚠️ 營收年增 {rev_g:.0f}%，業績在縮水，要注意")
    if roe < 8:      bear.append(f"😟 ROE {roe:.0f}%：公司賺錢效率偏低，可能競爭壓力大")
    if gm < 20:      bear.append(f"😟 毛利率 {gm:.0f}%：獲利空間窄，漲成本或降價都很傷")
    if ts <= -20:    bear.append("📉 技術面走弱，短期可能繼續下跌，進場要謹慎")
    if pv and pv > 2.5: bear.append(f"💸 PEG {pv:.1f}，股價已反映很多樂觀預期，如果業績不如預期會跌很多")
    if de > 100:     bear.append(f"⚠️ 負債比 {de:.0f}%，借了很多錢，利率高的時候壓力大")
    if beta > 1.8:   bear.append(f"🎢 Beta {beta:.1f}，這支股票很容易大漲大跌，小心情緒影響判斷")
    if not bear:     bear.append("目前沒有明顯負面警示，但市場永遠有黑天鵝，不能 all-in")

    # ── 中立客觀 ────────────────────────────────────────────
    neutral = [
        f"綜合評分：基本面 {fs}/100 | 技術面 {ts:+d}分",
        f"估值評級：{peg.get('verdict', '資料不足')}",
    ]
    fv = peg.get("fair_value")
    curr = info.get("currentPrice") or info.get("regularMarketPrice")
    if fv and curr:
        upside = (fv - curr) / curr * 100
        neutral.append(f"根據 PEG 模型，合理估值約 ${fv:.2f}，{'比現價還有 ' + f'{upside:.0f}% 上行空間' if upside > 0 else '現價已高於合理估值 ' + f'{-upside:.0f}%'}")
    neutral.append("⚠️ 任何分析都有侷限，建議分批買入、控制單股不超過總資金的 10%")

    return {"intro": intro, "bull": bull, "bear": bear, "neutral": neutral}


# ════════════════════════════════════════════════════════════
#  MARKET NEWS FEED
# ════════════════════════════════════════════════════════════

@st.cache_data(ttl=1800)
def get_market_news() -> list:
    sources = ["^GSPC","^TWII","^IXIC","NVDA","AAPL","META","TSLA","MSFT","2330.TW","AMD"]
    all_news = []
    for src in sources:
        try:
            for item in (yf.Ticker(src).news or [])[:4]:
                item["_src"] = src
                all_news.append(item)
        except Exception:
            pass
    seen, unique = set(), []
    for item in all_news:
        title = item.get("title","")
        if title and title not in seen:
            seen.add(title)
            unique.append(item)
    unique.sort(key=lambda x: x.get("providerPublishTime",0), reverse=True)
    return unique[:30]


# ════════════════════════════════════════════════════════════
#  CHARTS
# ════════════════════════════════════════════════════════════

def price_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    df = add_indicators(df)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.60, 0.20, 0.20], vertical_spacing=0.03)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name="K線",
        increasing=dict(line_color="#00d896", fillcolor="#00d896"),
        decreasing=dict(line_color="#ff4060", fillcolor="#ff4060"),
    ), row=1, col=1)
    for ma, c, n in [("MA5","#ffc842","MA5"),("MA20","#9b8cff","MA20"),("MA60","#ff8c42","MA60")]:
        if ma in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[ma], name=n,
                line=dict(color=c, width=1.3)), row=1, col=1)
    if "BB_upper" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper"], name="BB上",
            line=dict(color="#3d4f70", width=0.8, dash="dot")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_lower"], name="BB下",
            line=dict(color="#3d4f70", width=0.8, dash="dot"),
            fill="tonexty", fillcolor="rgba(61,79,112,0.08)"), row=1, col=1)
    if "RSI" in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI",
            line=dict(color="#9b8cff", width=1.5)), row=2, col=1)
        for lvl, c in [(70,"#ff4060"),(30,"#00d896")]:
            fig.add_hline(y=lvl, line_dash="dot", line_color=c, opacity=0.5, row=2, col=1)
    if "MACD" in df.columns:
        hc = ["#00d896" if v >= 0 else "#ff4060" for v in df["MACD_hist"].fillna(0)]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], name="MACD柱",
            marker_color=hc, opacity=0.8), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
            line=dict(color="#ffc842", width=1.3)), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="訊號",
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
        yaxis_title="相對報酬率 (%)",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=20, b=10, l=0, r=0),
    )
    fig.update_xaxes(gridcolor="#1a2035"); fig.update_yaxes(gridcolor="#1a2035")
    return fig


# ════════════════════════════════════════════════════════════
#  UI HELPERS
# ════════════════════════════════════════════════════════════

def badge(signal: str) -> str:
    m = {"BUY": '<span class="b-buy">BUY ▲</span>',
         "SELL":'<span class="b-sell">SELL ▼</span>',
         "HOLD":'<span class="b-hold">HOLD</span>'}
    return m.get(signal, signal)


def card(label, value, sub="", color="#f0f2f5"):
    return (f'<div class="card"><div class="card-label">{label}</div>'
            f'<div class="card-val" style="color:{color}">{value}</div>'
            f'<div class="card-sub">{sub}</div></div>')


def fmt(v, spec=".2f", pre="", suf=""):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    return f"{pre}{v:{spec}}{suf}"


def sec(title):
    st.markdown(f'<div class="sec">{title}</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def main():
    st.markdown("# 📈 AI 選股工作站")
    st.caption(f"數據來源：Yahoo Finance · 更新 {datetime.now().strftime('%Y-%m-%d %H:%M')}")

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
                f'<div style="color:{c};font-weight:700">{"▲" if idx["pct"]>=0 else "▼"} {idx["pct"]:+.2f}%</div>'
                f'</div>', unsafe_allow_html=True)

    # ── 風控紀律提醒 ──────────────────────────────────────────
    st.markdown("""
<div style="background:#1a0a00;border:1px solid #ff8c42;border-radius:12px;padding:12px 18px;margin:12px 0">
<div style="color:#ff8c42;font-weight:700;font-size:13px;margin-bottom:6px">⚡ 風控紀律提醒（每次買股前看一下）</div>
<div style="color:#c8a87a;font-size:12px;line-height:1.8">
💼 單一股票不超過總資金 <b>10%</b>&nbsp;&nbsp;
📉 虧損達 <b>-8%</b> 一定停損，不凹&nbsp;&nbsp;
📈 獲利超過 <b>+30%</b> 先賣一半落袋&nbsp;&nbsp;
🧘 大跌時不恐慌賣出，先看新聞確認原因
</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("---")

    tabs = st.tabs([
        "🔍 個股研究","📋 自選股掃描","📈 買入決策","📉 賣出決策",
        "⚖️ 股票比較","🚨 風險掃雷","💼 投資組合","📄 財報解讀",
        "⏳ 長期分析","🌐 主題清單","📰 今日新聞",
    ])

    # ──────────────────────────────────────────────────────
    # TAB 1: 個股研究
    # ──────────────────────────────────────────────────────
    with tabs[0]:
        c1, c2 = st.columns([3, 1])
        ticker = c1.text_input("股票代號", "AAPL", key="t1",
            help="美股: AAPL | 台股: 2330.TW").strip().upper()
        period = c2.selectbox("區間", ["3mo","6mo","1y","2y","5y"], index=2, label_visibility="hidden")

        if ticker:
            with st.spinner("載入中..."):
                info = enrich_info(ticker, get_info(ticker))
                df   = get_price(ticker, period)
                news = get_news(ticker)

            if df.empty:
                st.error(f"找不到 `{ticker}`，台股請加 .TW（如 2330.TW）"); return

            tech = tech_signal(df)
            fund = fund_score(info)
            peg  = peg_model(info)
            sig, sig_c = composite(tech, fund, peg)

            price = info.get("currentPrice") or info.get("regularMarketPrice") or df["Close"].iloc[-1]
            name  = info.get("shortName", ticker)

            c1,c2,c3,c4,c5 = st.columns(5)
            for col, lbl, val, sub, clr in [
                (c1, "現價", f"{price:.2f}", info.get("currency","USD"), "#f0f2f5"),
                (c2, "5日漲跌", f"{tech['ret5']:+.1f}%", f"20日 {tech['ret20']:+.1f}%",
                    "#00d896" if tech['ret5']>=0 else "#ff4060"),
                (c3, "技術評分", f"{tech['score']:+d}", badge(tech["signal"]), "#f0f2f5"),
                (c4, "基本面", f"{fund['score']}/100", peg.get("verdict",""), "#f0f2f5"),
                (c5, "綜合建議", sig, peg.get("verdict",""), sig_c),
            ]:
                col.markdown(card(lbl, val, sub, clr), unsafe_allow_html=True)

            st.plotly_chart(price_chart(df, ticker), use_container_width=True)

            # ── 新手白話文三角度分析 ──────────────────────────
            pa = plain_analysis(ticker, info, tech, fund, peg)
            with st.expander("🧑‍🎓 新手看這裡：白話文解析（看漲 / 看跌 / 中立）", expanded=True):
                st.markdown(f"**{pa['intro']}**")
                col_b, col_s, col_n = st.columns(3)
                with col_b:
                    st.markdown('<div style="background:#002a1a;border-radius:10px;padding:12px;min-height:160px">'
                                '<div style="color:#00d896;font-weight:700;margin-bottom:8px">📈 看漲角度</div>', unsafe_allow_html=True)
                    for pt in pa["bull"]:
                        st.markdown(f'<div style="color:#c0f0e0;font-size:13px;margin-bottom:6px">{pt}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with col_s:
                    st.markdown('<div style="background:#2a0010;border-radius:10px;padding:12px;min-height:160px">'
                                '<div style="color:#ff4060;font-weight:700;margin-bottom:8px">📉 看跌角度</div>', unsafe_allow_html=True)
                    for pt in pa["bear"]:
                        st.markdown(f'<div style="color:#f0c0c0;font-size:13px;margin-bottom:6px">{pt}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                with col_n:
                    st.markdown('<div style="background:#1a1a2a;border-radius:10px;padding:12px;min-height:160px">'
                                '<div style="color:#9b8cff;font-weight:700;margin-bottom:8px">⚖️ 中立客觀</div>', unsafe_allow_html=True)
                    for pt in pa["neutral"]:
                        st.markdown(f'<div style="color:#c0c0e0;font-size:13px;margin-bottom:6px">{pt}</div>', unsafe_allow_html=True)
                    st.markdown('</div>', unsafe_allow_html=True)

            t1,t2,t3,t4,t5 = st.tabs(["技術","基本面","估值","新聞","公司"])

            with t1:
                la, ra = st.columns(2)
                dfi = add_indicators(df); cur = dfi.iloc[-1]
                with la:
                    sec("均線與指標")
                    for ma_n, ma_k in [("MA5","MA5"),("MA20","MA20"),("MA60","MA60")]:
                        v = cur.get(ma_k)
                        if v and not pd.isna(v):
                            delta_str = "站上 ✅" if price > v else "跌破 ❌"
                            st.metric(ma_n, f"{v:.2f}", delta_str)
                    rsi = cur.get("RSI")
                    if rsi and not pd.isna(rsi):
                        st.metric("RSI", f"{rsi:.1f}",
                            "超買" if rsi>70 else "超賣" if rsi<30 else "健康區")
                with ra:
                    sec("訊號明細")
                    for lbl, clr in tech["details"]:
                        icon = "🟢" if clr=="green" else "🔴" if clr=="red" else "🟡"
                        st.markdown(f"{icon} {lbl}")
                    st.markdown("---")
                    st.markdown(f"**進場點**：`{tech['entry']}`")
                    st.markdown(f"**止損點**：`{tech['stop']}`（跌破後離場）")
                    st.markdown(f"**目標位**：`{tech['target']}`（2:1 風報比）")

            with t2:
                la, ra = st.columns(2)
                with la:
                    sec("財務指標")
                    for lbl, clr, desc in fund["details"]:
                        icon = "✅" if clr=="green" else "❌" if clr=="red" else "🟡"
                        st.markdown(f"{icon} **{lbl}** — {desc}")
                with ra:
                    sec("公司數據")
                    mc = info.get("marketCap")
                    st.metric("市值", f"${mc/1e9:.1f}B" if mc and mc>1e9 else fmt(mc,",.0f","$"))
                    st.metric("產業", info.get("industry","—"))
                    st.metric("板塊", info.get("sector","—"))
                    emp = info.get("fullTimeEmployees")
                    st.metric("員工數", f"{emp:,}" if emp else "—")

            with t3:
                la, ra = st.columns(2)
                with la:
                    sec("PEG 估值")
                    st.metric("本益比 P/E",    fmt(peg.get("pe"), ".1f", suf="x"))
                    st.metric("PEG 比率",      fmt(peg.get("peg"),".2f"))
                    st.metric("股價淨值比 P/B", fmt(peg.get("pb"), ".2f", suf="x"))
                    st.metric("P/S 比",        fmt(peg.get("ps"), ".2f", suf="x"))
                with ra:
                    sec("估值結論")
                    fv = peg.get("fair_value")
                    if fv:
                        upside = (fv - price) / price * 100
                        st.metric("合理估值 (PEG=1)", f"{fv:.2f}",
                            f"{'上行' if upside>0 else '下行'} {upside:+.1f}%")
                    st.metric("估值評級", peg.get("verdict","—"))
                    st.caption("PEG<0.8 低估 | 0.8-1.2 合理 | >2 高估\n合理價 = EPS × 成長率%")

            with t4:
                sec("最新財經新聞")
                for item in (news or []):
                    title = item.get("title","")
                    link  = item.get("link","#")
                    pub   = item.get("publisher","")
                    ts    = item.get("providerPublishTime",0)
                    dt    = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M") if ts else ""
                    st.markdown(
                        f'<div class="news-item">'
                        f'<div><a href="{link}" target="_blank">{title}</a></div>'
                        f'<div class="news-meta">{pub} · {dt}</div></div>',
                        unsafe_allow_html=True)
                if not news:
                    st.info("暫無新聞")

            with t5:
                sec("公司概況")
                desc = info.get("longBusinessSummary","")
                if desc:
                    st.write(desc[:800] + ("..." if len(desc)>800 else ""))
                st.markdown("---")
                c1,c2,c3 = st.columns(3)
                c1.metric("52週高點", fmt(info.get("fiftyTwoWeekHigh"),".2f"))
                c2.metric("52週低點", fmt(info.get("fiftyTwoWeekLow"),".2f"))
                c3.metric("Beta",     fmt(info.get("beta"),".2f"))
                dy = info.get("dividendYield")
                c1.metric("股息殖利率", f"{dy*100:.2f}%" if dy else "—")
                av = info.get("averageVolume")
                c2.metric("均量", f"{av/1e6:.1f}M" if av else "—")
                so = info.get("sharesOutstanding")
                c3.metric("流通股數", f"{so/1e9:.2f}B" if so else "—")

    # ──────────────────────────────────────────────────────
    # TAB 2: 自選股掃描
    # ──────────────────────────────────────────────────────
    with tabs[1]:
        sec("📋 自選股清單")
        gs_list, gs_status = load_gsheets_watchlist()
        if gs_list:
            st.success(gs_status)
            default_wl = "\n".join(gs_list)
        else:
            st.warning(gs_status)
            default_wl = "AAPL\nNVDA\nTSLA\nMSFT\nMETA\n2330.TW\n2317.TW\n2454.TW"

        col_in, col_btn = st.columns([4,1])
        wl_raw  = col_in.text_area("每行一個代號", default_wl, height=200)
        col_btn.markdown("<br><br><br>", unsafe_allow_html=True)
        run_scan = col_btn.button("🔎 開始掃描", type="primary", use_container_width=True)

        if run_scan:
            tickers = [t.strip().upper() for t in wl_raw.split("\n") if t.strip()]
            rows = []
            prog = st.progress(0, "掃描中...")
            for i, t in enumerate(tickers):
                try:
                    inf = enrich_info(t, get_info(t)); dfx = get_price(t, "3mo")
                    if dfx.empty: continue
                    tc = tech_signal(dfx); fc = fund_score(inf); pc = peg_model(inf)
                    sg, _ = composite(tc, fc, pc)
                    px = inf.get("currentPrice") or inf.get("regularMarketPrice") or dfx["Close"].iloc[-1]
                    rows.append({"代碼":t,"名稱":(inf.get("shortName","")or"")[:16],
                                 "現價":f"{px:.2f}","5日%":f"{tc.get('ret5',0):+.1f}%",
                                 "技術":tc["signal"],"基本面":f"{fc['score']}/100",
                                 "PEG":f"{pc['peg']:.2f}" if pc.get("peg") else "—",
                                 "估值":pc.get("verdict","—"),"RSI":f"{tc['rsi']:.0f}" if tc.get("rsi") else "—",
                                 "綜合建議":sg})
                except Exception:
                    pass
                prog.progress((i+1)/len(tickers), f"掃描 {t}...")
            prog.empty()
            if rows:
                wdf = pd.DataFrame(rows)
                def cmap(v):
                    if "強力買進" in str(v): return "background:#002a1a;color:#00d896"
                    if "值得關注" in str(v): return "background:#00200f;color:#4ecf8c"
                    if "建議避開" in str(v): return "background:#2a0010;color:#ff4060"
                    if "謹慎" in str(v):     return "background:#2a1500;color:#ff8c42"
                    return ""
                st.dataframe(wdf.style.map(cmap, subset=["綜合建議"]),
                             use_container_width=True, height=380)
                st.download_button("⬇️ 下載 CSV",
                    wdf.to_csv(index=False, encoding="utf-8-sig"),
                    f"scan_{datetime.now():%Y%m%d}.csv", "text/csv")

    # ──────────────────────────────────────────────────────
    # TAB 3: 買入決策
    # ──────────────────────────────────────────────────────
    with tabs[2]:
        sec("📈 買入決策分析")
        st.caption("告訴你為什麼推薦或不推薦，以及什麼時候才是更好的進場時機")
        c1,c2,c3,c4 = st.columns(4)
        b_t = c1.text_input("股票代號","NVDA",key="bt").strip().upper()
        b_p = c2.number_input("目標買入價（選填，0=用現價）",0.0,step=0.5,key="bp")
        b_y = c3.selectbox("計劃持有",["<1年","1-2年","3-5年",">5年"],index=2,key="by")
        b_r = c4.selectbox("風險承受度",["低 (-8%)","中 (-15%)","高 (-30%)"],index=1,key="br")

        if st.button("🎯 分析買入時機", type="primary", key="b_go"):
            with st.spinner("分析中..."):
                bi = enrich_info(b_t, get_info(b_t)); bd = get_price(b_t, "1y")
            tc = tech_signal(bd); fc = fund_score(bi); pc = peg_model(bi)
            curr = bi.get("currentPrice") or bi.get("regularMarketPrice") or (bd["Close"].iloc[-1] if not bd.empty else 0)

            ymap = {"<1年":0.5,"1-2年":1.5,"3-5年":4,">5年":7}
            yrs  = ymap.get(b_y, 3)
            is_short = yrs < 2

            score = 0
            pros  = []
            cons  = []

            # --- 1. 目標價 vs 現價 ---
            if b_p and curr and b_p > 0:
                mg = (curr - b_p) / b_p * 100
                if mg <= -5:   score += 20; pros.append(f"目標買入價比現價低 {-mg:.1f}%，有安全邊際")
                elif mg <= 0:  score += 10; pros.append(f"目標買入價接近現價，位置合理")
                elif mg <= 5:  score +=  3; cons.append(f"目標買入價比現價高 {mg:.1f}%，建議等回調")
                else:          score -= 15; cons.append(f"目標買入價比現價高 {mg:.1f}%，大幅溢價，建議重設目標")

            # --- 2. 持有期間加分 ---
            if yrs >= 5:
                score += 15; pros.append("計劃持有 5 年以上，時間是你的盟友，短期波動影響很小")
            elif yrs >= 2:
                score +=  8; pros.append("中期持有（1–5 年），需定期追蹤基本面變化")
            else:
                pros.append("短期持有（< 1 年），技術面是關鍵，記得設好停損點")

            # --- 3. 基本面 ---
            fs = fc["score"]
            if is_short:
                if fs >= 60:   score += 10; pros.append(f"基本面 {fs}/100 良好（短線交易者參考）")
                elif fs < 40:  score -=  5; cons.append(f"基本面 {fs}/100 偏弱，短線需更謹慎")
            else:
                if fs >= 70:   score += 25; pros.append(f"基本面 {fs}/100 優良，長期持有底氣足")
                elif fs >= 55: score += 12; pros.append(f"基本面 {fs}/100 中等，需持續觀察")
                elif fs >= 40: score -=  5; cons.append(f"基本面 {fs}/100 偏弱，長期持有有隱患")
                else:          score -= 20; cons.append(f"基本面 {fs}/100 差，不建議長期押注")

            # --- 4. 技術面 ---
            ts  = tc["score"]
            rsi = tc.get("rsi")
            if is_short:
                if ts >= 40:   score += 25; pros.append(f"技術評分 {ts:+d}，短線進場時機良好")
                elif ts >= 0:  score +=  5; pros.append(f"技術評分 {ts:+d}，技術面中性")
                elif ts >= -20:score -= 10; cons.append(f"技術評分 {ts:+d}，短線偏弱，可能繼續下探")
                else:          score -= 20; cons.append(f"技術評分 {ts:+d}，短線明顯偏空，建議等訊號轉多再進")
            else:
                if ts >= 40:   score += 15; pros.append(f"技術評分 {ts:+d}，目前趨勢向上")
                elif ts >= 0:  score +=  5; pros.append(f"技術評分 {ts:+d}，技術面中性，可分批布局")
                elif ts >= -20:score -=  5; cons.append(f"技術評分 {ts:+d}，短期走弱，但長線可等落底再買")
                else:          score -= 10; cons.append(f"技術評分 {ts:+d}，趨勢偏空，建議等反彈確認再進")

            # --- 5. RSI ---
            if rsi:
                if rsi < 30:   score += 15; pros.append(f"RSI {rsi:.0f} 超賣，歷史上是相對低點，反彈機率高")
                elif rsi < 42: score +=  8; pros.append(f"RSI {rsi:.0f} 偏低，有反彈空間")
                elif rsi > 75: score -= 10; cons.append(f"RSI {rsi:.0f} 超買，短線可能回調，不是最佳入場點")
                elif rsi > 65: score -=  5; cons.append(f"RSI {rsi:.0f} 偏高，追高有風險")

            # --- 6. 估值 PEG ---
            pv = pc.get("peg")
            if pv:
                if pv < 0.8:   score += 20; pros.append(f"PEG {pv:.2f}，明顯低估，成長被市場忽略")
                elif pv < 1.3: score += 12; pros.append(f"PEG {pv:.2f}，估值合理")
                elif pv < 2.0: score +=  0; cons.append(f"PEG {pv:.2f}，估值偏高，成長需維持才撐得住")
                else:          score -= 15; cons.append(f"PEG {pv:.2f}，估值過高，需要極高成長率才合理")

            score = max(-100, min(100, score))

            # 結論門檻因持有期調整
            if is_short:
                if score >= 55:  verdict, vc = "✅ 短線可以進場", "#00d896"
                elif score >= 20: verdict, vc = "⏳ 等待訊號確認", "#ffc842"
                else:             verdict, vc = "❌ 短線不建議進", "#ff4060"
            else:
                if score >= 40:  verdict, vc = "✅ 建議買進", "#00d896"
                elif score >= 10: verdict, vc = "⏳ 等待更好時機", "#ffc842"
                else:             verdict, vc = "❌ 目前不建議", "#ff4060"

            st.markdown(
                f'<div class="card" style="border-color:{vc};text-align:center;padding:20px">'
                f'<div style="font-size:28px;font-weight:800;color:{vc}">{verdict}</div>'
                f'<div class="card-sub" style="margin-top:8px">綜合評分 {score:+d}/100｜{b_y}持有策略</div></div>',
                unsafe_allow_html=True)

            col_pro, col_con = st.columns(2)
            with col_pro:
                sec("✅ 支持買入的理由")
                if pros:
                    for p in pros:
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid #00d896;padding:8px 12px">'
                            f'<span class="green">▲</span> {p}</div>', unsafe_allow_html=True)
                else:
                    st.markdown("目前沒有明顯支持買入的訊號")
            with col_con:
                sec("❌ 現在買需要注意的風險")
                if cons:
                    for c_item in cons:
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid #ff4060;padding:8px 12px">'
                            f'<span class="red">▼</span> {c_item}</div>', unsafe_allow_html=True)
                else:
                    st.markdown("目前沒有明顯警示，可考慮進場")

            # 什麼時候才比較適合買
            sec("🎯 什麼時候比較適合買？")
            tips = []
            if rsi and rsi > 60:
                target_rsi = 35 if rsi > 72 else 45
                tips.append(f"等 RSI 回落到 {target_rsi} 以下再進，勝率更高")
            if pv and pv > 1.5:
                tips.append(f"等 PEG 降到 1.3 以下（估值回歸合理）再布局")
            if ts < 0 and not bd.empty:
                df_ind = add_indicators(bd)
                ma20 = df_ind["MA20"].iloc[-1] if not pd.isna(df_ind["MA20"].iloc[-1]) else None
                ma60 = df_ind["MA60"].iloc[-1] if not pd.isna(df_ind["MA60"].iloc[-1]) else None
                if ma20 and curr < ma20:
                    tips.append(f"等股價站回 MA20（約 ${ma20:.2f}）確認短線趨勢轉多")
                if ma60 and curr < ma60:
                    tips.append(f"等股價站回 MA60（約 ${ma60:.2f}）確認中期趨勢轉多")
                tips.append("等 MACD 出現金叉（MACD 線由下往上穿越訊號線）再進場")
            if not bd.empty:
                support = bd.tail(20)["Low"].min()
                if curr and curr > support * 1.06:
                    tips.append(f"若股價回測支撐區 ${support:.2f} 附近（近20日低點），可考慮分批買入")
            if not is_short and fs < 50:
                tips.append("等下季財報確認基本面是否改善，再決定是否投入")
            if not tips:
                if score >= 40:
                    tips.append("目前指標偏正面，可依自己的成本目標分批進場，不必等待")
                else:
                    tips.append("目前多項指標偏弱，建議觀望 4–8 週後重新評估")
            for tip in tips:
                st.markdown(f"• {tip}")

            # 近期走勢方向
            sec("📊 近期走勢方向")
            if not bd.empty and len(bd) >= 20:
                avg5  = bd["Close"].iloc[-5:].mean()
                avg20 = bd["Close"].iloc[-20:].mean()
                trend_dir = "上升" if avg5 > avg20 else "下降"
                tc2 = "#00d896" if trend_dir == "上升" else "#ff4060"
                ret5  = tc.get("ret5", 0)
                ret20 = tc.get("ret20", 0)
                st.markdown(
                    f"短期均線 vs 中期均線：趨勢 <span style='color:{tc2}'><b>{trend_dir}中</b></span>，"
                    f"5日漲跌 **{ret5:+.1f}%**，20日漲跌 **{ret20:+.1f}%**",
                    unsafe_allow_html=True)

            if not bd.empty:
                st.plotly_chart(price_chart(bd, b_t), use_container_width=True)

    # ──────────────────────────────────────────────────────
    # TAB 4: 賣出決策
    # ──────────────────────────────────────────────────────
    with tabs[3]:
        sec("📉 賣出決策分析")
        st.caption("輸入持倉資訊，判斷投資論文是否仍成立，給出保守/平衡/積極三種賣法")
        s1,s2,s3 = st.columns(3)
        s_t = s1.text_input("持有股票","AAPL",key="st").strip().upper()
        s_c = s2.number_input("成本價($)",0.0,step=0.5,key="sc")
        s_q = s3.number_input("持有股數",0,step=1,key="sq")

        if st.button("🔍 分析持倉", type="primary", key="s_go"):
            with st.spinner("分析中..."):
                si = get_info(s_t); sd = get_price(s_t,"1y")
            curr = si.get("currentPrice") or si.get("regularMarketPrice") or (sd["Close"].iloc[-1] if not sd.empty else 0)
            gp = (curr - s_c) / s_c * 100 if s_c else 0
            ga = (curr - s_c) * s_q if s_c and s_q else 0
            sc = tech_signal(sd); sf = fund_score(si); sp = peg_model(si)
            fv = sp.get("fair_value")

            gc = "#00d896" if gp>=0 else "#ff4060"
            st.markdown(
                f'<div class="card"><div style="display:flex;justify-content:space-between">'
                f'<div><div class="card-label">持倉損益</div>'
                f'<div style="color:{gc};font-size:28px;font-weight:800">{gp:+.1f}%</div></div>'
                f'<div style="text-align:right"><div class="card-label">市值損益</div>'
                f'<div style="color:{gc};font-size:24px;font-weight:700">{"${:,.0f}".format(ga) if ga else "—"}</div></div>'
                f'</div></div>', unsafe_allow_html=True)

            sec("三種賣法")
            strats = [
                ("🛡️ 保守",
                 "賣出 50% 部位" if gp>20 or sc["score"]<-20 else f"設停損 {s_c*0.92:.2f}，停利 {s_c*1.25:.2f}",
                 "落袋為安，保留一半觀察"),
                ("⚖️ 平衡",
                 "減碼 30%" if (fv and curr>fv*1.2) else "繼續持有，追蹤季報",
                 f"現價{'高於' if fv and curr>fv*1.2 else '接近'}合理估值 {fv:.2f}" if fv else "基本面未出現破裂訊號"),
                ("🚀 積極",
                 "全數持有甚至加碼" if sf["score"]>=70 and gp<50 else "賣出 80%，留 20% 看長線",
                 f"基本面{sf['score']}/100，{'成長邏輯完整' if sf['score']>=70 else '已大幅獲利'}"),
            ]
            for icon_type, action, reason in strats:
                st.markdown(
                    f'<div class="card">'
                    f'<div style="color:#6b7a99;font-weight:600">{icon_type}</div>'
                    f'<div style="color:#f0f2f5;font-size:16px;font-weight:700;margin:4px 0">{action}</div>'
                    f'<div style="color:#9b8cff;font-size:13px">{reason}</div>'
                    f'</div>', unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────
    # TAB 5: 股票比較
    # ──────────────────────────────────────────────────────
    with tabs[4]:
        sec("⚖️ 多股比較（最多 4 支）")
        cc = st.columns(4)
        defaults = ["AAPL","MSFT","GOOGL","META"]
        cmp_tks = [c.text_input(f"股票 {i+1}", d, key=f"cmp{i}").strip().upper()
                   for i,( c,d) in enumerate(zip(cc, defaults))]

        if st.button("📊 開始比較", type="primary", key="cmp_go"):
            cdata = []
            with st.spinner("載入..."):
                for tkr in [t for t in cmp_tks if t]:
                    inf = get_info(tkr); dfx = get_price(tkr,"1y")
                    if dfx.empty: continue
                    tc = tech_signal(dfx); fc = fund_score(inf); pc = peg_model(inf)
                    sg, _ = composite(tc, fc, pc)
                    px = inf.get("currentPrice") or inf.get("regularMarketPrice") or dfx["Close"].iloc[-1]
                    cdata.append({"代碼":tkr,"名稱":(inf.get("shortName","")or"")[:14],
                                  "現價":px,
                                  "ROE%":inf.get("returnOnEquity",None) and inf["returnOnEquity"]*100,
                                  "毛利率%":inf.get("grossMargins",None) and inf["grossMargins"]*100,
                                  "營收成長%":inf.get("revenueGrowth",None) and inf["revenueGrowth"]*100,
                                  "淨利率%":inf.get("profitMargins",None) and inf["profitMargins"]*100,
                                  "P/E":inf.get("trailingPE"),"PEG":pc.get("peg"),
                                  "Beta":inf.get("beta"),"基本面":fc["score"],"技術":tc["score"],
                                  "建議":sg,"df":dfx})

            if cdata:
                st.plotly_chart(comparison_chart([(d["代碼"],d["df"]) for d in cdata]),
                                use_container_width=True)
                show_cols = ["代碼","名稱","現價","ROE%","毛利率%","營收成長%","淨利率%","P/E","PEG","Beta","基本面","技術","建議"]
                cdf = pd.DataFrame([{k:v for k,v in d.items() if k!="df"} for d in cdata])[show_cols]
                for nc in ["ROE%","毛利率%","營收成長%","淨利率%","P/E","PEG","Beta","基本面","技術"]:
                    cdf[nc] = pd.to_numeric(cdf[nc],errors="coerce").round(1)
                st.dataframe(cdf.style.highlight_max(
                    subset=["ROE%","毛利率%","營收成長%","淨利率%","基本面","技術"], color="#002a1a"
                ).highlight_min(subset=["PEG","P/E","Beta"], color="#002a1a"),
                use_container_width=True)

                sec("綜合排名")
                ranked = sorted(cdata, key=lambda x: x["基本面"]*0.6+x["技術"]*0.4, reverse=True)
                for i, d in enumerate(ranked):
                    medal = ["🥇","🥈","🥉","4️⃣"][i]
                    st.markdown(f"{medal} **{d['代碼']}** {d['名稱']} — 基本面 {d['基本面']}/100 | {d['建議']}")

    # ──────────────────────────────────────────────────────
    # TAB 6: 風險掃雷
    # ──────────────────────────────────────────────────────
    with tabs[5]:
        sec("🚨 買前風險掃雷")
        r_t = st.text_input("股票代號","TSLA",key="rt").strip().upper()
        if st.button("🔍 掃描風險", type="primary", key="r_go"):
            with st.spinner("掃描中..."):
                ri = get_info(r_t); rd = get_price(r_t,"1y")
                risks = risk_scan(ri, rd)
            hi = [x for x in risks if x[1]=="h"]
            mi = [x for x in risks if x[1]=="m"]
            lo = [x for x in risks if x[1]=="l"]
            c1,c2,c3 = st.columns(3)
            c1.metric("高風險","🔴 "+str(len(hi))+" 項" if hi else "✅ 無")
            c2.metric("中風險","🟠 "+str(len(mi))+" 項" if mi else "✅ 無")
            c3.metric("低/無風險","🟢 "+str(len(lo))+" 項")
            for group, title, border in [
                (hi,"🔴 高風險","#ff4060"),(mi,"🟠 中風險","#ff8c42"),(lo,"🟢 低風險","#00d896")
            ]:
                if group:
                    sec(title)
                    for lbl, _, desc in group:
                        st.markdown(
                            f'<div class="card" style="border-left:3px solid {border}">'
                            f'<div style="color:#f0f2f5;font-weight:600">{lbl}</div>'
                            f'<div style="color:#6b7a99;font-size:13px;margin-top:3px">💡 {desc}</div></div>',
                            unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────
    # TAB 7: 投資組合
    # ──────────────────────────────────────────────────────
    with tabs[6]:
        sec("💼 投資組合配置建議")
        budget   = st.number_input("可投資資金($)",1000,step=500,value=10000,key="pf_b")
        pf_raw   = st.text_area("候選股票（每行一個）","AAPL\nMSFT\nNVDA\n2330.TW",key="pf_t")
        pf_risk  = st.radio("風險偏好",["成長優先","均衡","防禦保守"],horizontal=True,key="pf_r")

        if st.button("💡 計算配置", type="primary", key="pf_go"):
            pf_tks = [t.strip().upper() for t in pf_raw.split("\n") if t.strip()]
            scores = []
            with st.spinner("計算中..."):
                for t in pf_tks:
                    inf = get_info(t); dfx = get_price(t,"6mo")
                    fc = fund_score(inf); tc = tech_signal(dfx)
                    scores.append({"ticker":t,"name":(inf.get("shortName","")or t)[:14],
                                   "fs":fc["score"],"ts":tc["score"],"beta":inf.get("beta",1) or 1})
            wfn = {
                "成長優先": lambda x: x["fs"]*0.5 + x["ts"]*0.5,
                "均衡":     lambda x: x["fs"]*0.7 + x["ts"]*0.3,
                "防禦保守": lambda x: x["fs"]*0.9 - (x["beta"]-1)*10,
            }[pf_risk]
            for s in scores: s["w"] = max(0, wfn(s))
            tw = sum(s["w"] for s in scores) or 1
            cash_p = {"成長優先":5,"均衡":10,"防禦保守":20}[pf_risk]
            inv_p  = 100 - cash_p
            rows = []
            for s in scores:
                ap = s["w"]/tw*inv_p
                rows.append({"代碼":s["ticker"],"名稱":s["name"],"基本面":s["fs"],
                             "技術":s["ts"],"配置比例":f"{ap:.1f}%","建議金額":f"${budget*ap/100:,.0f}"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True)
            st.success(f"💵 建議保留現金：{cash_p}% = ${budget*cash_p/100:,.0f}")

    # ──────────────────────────────────────────────────────
    # TAB 8: 財報解讀
    # ──────────────────────────────────────────────────────
    with tabs[7]:
        sec("📄 財報快速解讀")
        e_t = st.text_input("股票代號","AAPL",key="et").strip().upper()
        if st.button("📊 解讀財報", type="primary", key="e_go"):
            with st.spinner("載入財報..."):
                ei = get_info(e_t); ef = get_financials(e_t)
            sec("本期關鍵數字")
            rev = ei.get("totalRevenue"); rg = ei.get("revenueGrowth")
            eps = ei.get("trailingEps");  pm = ei.get("profitMargins")
            gm  = ei.get("grossMargins"); tpe = ei.get("trailingPE"); fpe = ei.get("forwardPE")
            eg  = ei.get("earningsGrowth")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("年化收入", f"${rev/1e9:.1f}B" if rev else "—", f"{rg*100:+.1f}% YoY" if rg else "")
            c2.metric("EPS (TTM)", f"${eps:.2f}" if eps else "—")
            c3.metric("淨利率", f"{pm*100:.1f}%" if pm else "—")
            c4.metric("毛利率", f"{gm*100:.1f}%" if gm else "—")
            sec("前瞻指引")
            c1,c2,c3 = st.columns(3)
            c1.metric("當前 P/E",   f"{tpe:.1f}x" if tpe else "—")
            c2.metric("遠期 P/E",   f"{fpe:.1f}x" if fpe else "—")
            c3.metric("盈餘成長預估", f"{eg*100:+.1f}%" if eg else "—")
            sec("財報評估")
            if rg and rg>0.15:  st.markdown("✅ 營收強勁成長")
            elif rg and rg<0:    st.markdown("❌ 營收衰退，需警惕")
            if pm and pm>0.15:   st.markdown("✅ 淨利率健康")
            if fpe and tpe and fpe<tpe: st.markdown("✅ 遠期估值優於當前，市場預期成長")
            if ef.get("earnings") is not None:
                try:
                    edf = pd.DataFrame(ef["earnings"])
                    if not edf.empty:
                        sec("歷史 EPS"); st.dataframe(edf.tail(8), use_container_width=True)
                except Exception:
                    pass

    # ──────────────────────────────────────────────────────
    # TAB 9: 長期分析
    # ──────────────────────────────────────────────────────
    with tabs[8]:
        sec("⏳ 長期持有分析")
        lt_t = st.text_input("股票代號","MSFT",key="ltt").strip().upper()
        lt_y = st.selectbox("計劃持有",["5年","10年","15年"],key="lty")

        if st.button("🔭 分析長期價值", type="primary", key="lt_go"):
            with st.spinner("分析中..."):
                li = get_info(lt_t); ld = get_price(lt_t,"5y")
                lf = fund_score(li); lp = peg_model(li)
            sec("護城河評估")
            gm = li.get("grossMargins",0) or 0; roe = li.get("returnOnEquity",0) or 0
            if gm>0.5:  st.markdown("✅ **高毛利率 >50%** — 定價能力強，有成本護城河")
            if roe>0.2:  st.markdown("✅ **高 ROE >20%** — 資本效率高，競爭優勢明顯")
            mc = li.get("marketCap",0) or 0
            if mc>100e9: st.markdown("✅ **大市值龍頭** — 規模效應強，市場份額穩固")
            de = li.get("debtToEquity")
            if de and de<50: st.markdown("✅ **低負債** — 財務穩健，抗風險能力強")

            sec("長期報酬估算")
            cp = li.get("currentPrice") or li.get("regularMarketPrice")
            eg = li.get("earningsGrowth") or li.get("revenueGrowth") or 0.10
            yrs = int(lt_y.replace("年",""))
            if cp and eg>0:
                c1,c2,c3 = st.columns(3)
                bull = cp*(1+eg*1.2)**yrs; base = cp*(1+eg*0.8)**yrs; bear = cp*(1+max(eg-0.05,0.02))**yrs
                c1.metric("樂觀",f"${bull:.0f}",f"+{(bull/cp-1)*100:.0f}%")
                c2.metric("基本",f"${base:.0f}",f"+{(base/cp-1)*100:.0f}%")
                c3.metric("悲觀",f"${bear:.0f}",f"+{(bear/cp-1)*100:.0f}%")
            sec("論文破裂信號")
            st.markdown("""
- 🔴 連續 2 季 ROE 低於 10%
- 🔴 毛利率連續下滑超過 5 個百分點
- 🔴 核心業務被顛覆性技術替代
- 🔴 管理層異動（CEO/CFO 更換）
- 🟡 自由現金流連續 3 季下滑
- 🟡 負債比突破 150%
            """)

    # ──────────────────────────────────────────────────────
    # TAB 10: 主題清單
    # ──────────────────────────────────────────────────────
    with tabs[9]:
        sec("🌐 主題股票清單")
        THEMES = {
            "🤖 AI / 半導體": ["NVDA","AMD","AVGO","AMAT","ASML","2330.TW","2454.TW"],
            "☁️ 科技 / 雲端":  ["MSFT","GOOGL","AMZN","META","CRM","SNOW"],
            "🏥 醫療生技":     ["JNJ","UNH","ABBV","LLY","MRNA","PFE"],
            "⚡ 清潔能源":     ["ENPH","FSLR","NEE","PLUG","BEP"],
            "💰 高股息":       ["KO","PG","JNJ","VZ","T","MO","XOM"],
            "🏦 金融科技":     ["V","MA","PYPL","SQ","NU"],
            "🛒 消費零售":     ["AMZN","WMT","COST","TGT","SBUX"],
            "🌏 台股精選":     ["2330.TW","2317.TW","2454.TW","3008.TW","2382.TW"],
        }
        th_sel = st.selectbox("選擇主題", list(THEMES.keys()), key="th_sel")
        if st.button("🔎 掃描此主題", type="primary", key="th_go"):
            rows = []; prog = st.progress(0); tks = THEMES[th_sel]
            for i, t in enumerate(tks):
                try:
                    inf = get_info(t); dfx = get_price(t,"3mo")
                    if dfx.empty: continue
                    tc = tech_signal(dfx); fc = fund_score(inf); pc = peg_model(inf)
                    sg,_ = composite(tc,fc,pc)
                    px = inf.get("currentPrice") or inf.get("regularMarketPrice") or dfx["Close"].iloc[-1]
                    rows.append({"代碼":t,"公司":(inf.get("shortName","")or"")[:16],
                                 "現價":f"{px:.2f}","產業":(inf.get("industry","")or"")[:20],
                                 "基本面":f"{fc['score']}/100","技術":tc["signal"],
                                 "PEG":f"{pc['peg']:.2f}" if pc.get("peg") else "—",
                                 "5日%":f"{tc.get('ret5',0):+.1f}%","建議":sg})
                except Exception:
                    pass
                prog.progress((i+1)/len(tks))
            prog.empty()
            if rows:
                thdf = pd.DataFrame(rows)
                def cmap2(v):
                    if "強力買進" in str(v): return "background:#002a1a;color:#00d896"
                    if "值得關注" in str(v): return "background:#00200f;color:#4ecf8c"
                    if "建議避開" in str(v): return "background:#2a0010;color:#ff4060"
                    return ""
                st.dataframe(thdf.style.map(cmap2,subset=["建議"]),
                             use_container_width=True, height=400)

    # ──────────────────────────────────────────────────────
    # TAB 11: 今日財經新聞
    # ──────────────────────────────────────────────────────
    with tabs[10]:
        sec("📰 今日財經新聞")
        st.caption("自動彙整美股大盤、台股、熱門股最新動態，每 30 分鐘更新一次")

        col_filter, col_refresh = st.columns([4,1])
        news_lang = col_filter.radio("篩選",["全部","美股相關","台股相關"],
                                     horizontal=True, key="news_filter")
        if col_refresh.button("🔄 立即更新", key="news_refresh"):
            st.cache_data.clear()

        with st.spinner("載入新聞..."):
            all_news = get_market_news()

        tw_sources = {"^TWII","2330.TW"}
        us_sources = {"^GSPC","^IXIC","NVDA","AAPL","META","TSLA","MSFT","AMD"}

        if news_lang == "台股相關":
            filtered = [n for n in all_news if n.get("_src") in tw_sources]
        elif news_lang == "美股相關":
            filtered = [n for n in all_news if n.get("_src") in us_sources]
        else:
            filtered = all_news

        if not filtered:
            st.info("暫時沒有新聞，請稍後再試")
        else:
            src_label = {
                "^GSPC":"S&P500","^TWII":"台灣加權","^IXIC":"NASDAQ",
                "NVDA":"NVDA","AAPL":"AAPL","META":"META",
                "TSLA":"TSLA","MSFT":"MSFT","2330.TW":"台積電","AMD":"AMD",
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
                    f'{pub} · {dt}</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    st.caption("⚠️ 本工具僅供研究與教育目的，不構成任何投資建議。投資有風險，請審慎評估。")


if __name__ == "__main__":
    main()
