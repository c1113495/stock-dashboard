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
.stApp{background:#0a1020}
.main .block-container{padding-top:1rem;max-width:1400px}
.card{background:#0f1a2e;border:1px solid #1e3050;border-radius:10px;padding:12px 16px;margin-bottom:8px}
.card-label{color:#7fa8c8;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.card-val{color:#cce0ff;font-size:22px;font-weight:800;margin:3px 0}
.card-sub{font-size:13px;color:#8ab8d8}
.sec{color:#5b9cf6;font-size:15px;font-weight:700;border-left:3px solid #5b9cf6;padding:2px 0 2px 10px;margin:16px 0 8px}
.green{color:#3ecf8e}.red{color:#f07070}.yellow{color:#f0b840}.purple{color:#5b9cf6}
.b-buy{background:#0a2818;color:#3ecf8e;border:1px solid #3ecf8e;padding:2px 12px;border-radius:20px;font-weight:700;font-size:12px}
.b-sell{background:#281010;color:#f07070;border:1px solid #f07070;padding:2px 12px;border-radius:20px;font-weight:700;font-size:12px}
.b-hold{background:#281f00;color:#f0b840;border:1px solid #f0b840;padding:2px 12px;border-radius:20px;font-weight:700;font-size:12px}
.news-item{border-left:3px solid #1e3050;padding:8px 14px;margin:5px 0;background:#0f1a2e;border-radius:0 8px 8px 0}
.news-item a{color:#b8d8f8;text-decoration:none;font-size:14px;font-weight:500}
.news-meta{color:#7fa8c8;font-size:11px;margin-top:3px}
.risk-h{background:#281010;color:#f07070;padding:1px 8px;border-radius:4px;font-size:12px;font-weight:600}
.risk-m{background:#281a00;color:#f0a060;padding:1px 8px;border-radius:4px;font-size:12px;font-weight:600}
.risk-l{background:#0a2818;color:#3ecf8e;padding:1px 8px;border-radius:4px;font-size:12px;font-weight:600}
.idx-bar{display:flex;gap:20px;align-items:center;flex-wrap:wrap;padding:8px 4px;border-bottom:1px solid #1e3050;margin-bottom:10px}
.idx-item{display:flex;align-items:center;gap:6px}
.idx-name{color:#7fa8c8;font-size:11px;font-weight:600}
.idx-price{color:#cce0ff;font-size:13px;font-weight:700}
.stTabs [data-baseweb="tab-list"]{background:#0f1a2e;border-radius:10px;padding:3px;gap:2px}
.stTabs [data-baseweb="tab"]{border-radius:7px;color:#7fa8c8;font-weight:600}
.stTabs [aria-selected="true"]{background:#1e3050!important;color:#cce0ff!important}
[data-testid="stMetricLabel"]{color:#7fa8c8!important}
[data-testid="stMetricValue"]{color:#cce0ff!important}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-thumb{background:#1e3050;border-radius:3px}
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
        raw = yf.Ticker(ticker).news or []
        result = []
        for item in list(raw)[:10]:
            parsed = _parse_news_item(item)
            if parsed:
                result.append(parsed)
        return result
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
    if rev_g > 20:
        bull.append(f"📈 **營收暴增 {rev_g:.0f}%**\n業績火熱，代表越來越多人在買它的產品或服務。這種成長速度通常會吸引更多投資人進場，推升股價。")
    elif rev_g > 5:
        bull.append(f"📈 **營收穩定成長 {rev_g:.0f}%**\n雖然不是爆發式成長，但穩定增加代表公司體質健康，長期持有比較放心。")
    if roe > 20:
        bull.append(f"💪 **ROE {roe:.0f}%（非常優秀）**\nROE 就是「公司幫你的錢賺錢的效率」。20% 以上代表每投入 100 元，公司能賺回 {roe:.0f} 元。這是巴菲特最愛看的指標之一。")
    elif roe > 15:
        bull.append(f"💪 **ROE {roe:.0f}%（良好）**\n公司獲利能力不錯，用股東的資金創造了合理的回報。")
    if gm > 50:
        bull.append(f"🏰 **毛利率 {gm:.0f}%（護城河級別）**\n毛利率這麼高，代表這家公司的產品「別人很難搶走」，它可以自訂高價而客戶還是買單。例如蘋果、輝達都是這種類型。")
    elif gm > 30:
        bull.append(f"✅ **毛利率 {gm:.0f}%（有競爭力）**\n產品有一定定價能力，不容易被價格戰打倒。")
    if ts >= 30:
        bull.append("📊 **技術面走強**\n從K線、均線、MACD等指標來看，近期買方力量大於賣方，短期股價動能偏多，進場時機相對較好。")
    if pv and pv < 1:
        bull.append(f"💰 **PEG {pv:.2f}（低估）**\nPEG 小於 1 代表「股價比公司的成長速度還便宜」，簡單說就是撿到便宜。這種機會不常有。")
    if de < 30:
        bull.append(f"🛡️ **負債比 {de:.0f}%（財務穩健）**\n公司幾乎沒有借錢，不需要擔心利率上升或景氣下滑時還不起債的問題，抗風險能力強。")
    if not bull:
        bull.append("⚪ 目前沒有特別亮眼的正面訊號，建議觀望，等下一季財報或技術訊號更明確後再考慮進場。")

    # ── 看跌角度 ────────────────────────────────────────────
    bear = []
    if rev_g < 0:
        bear.append(f"⚠️ **營收衰退 {rev_g:.0f}%**\n業績在縮水，代表賣出去的東西越來越少，或是市場需求在降低。這是基本面惡化的警訊，要認真看待。")
    if roe < 8:
        bear.append(f"😟 **ROE {roe:.0f}%（偏低）**\n公司用你的錢賺錢效率不高，可能是競爭壓力大、成本過高、或管理不善。長期持有報酬可能有限。")
    if gm < 20:
        bear.append(f"😟 **毛利率 {gm:.0f}%（空間很窄）**\n獲利空間太薄，一旦原物料漲價、或競爭對手降價搶市，這家公司就會很難看。")
    if ts <= -20:
        bear.append("📉 **技術面走弱**\n均線、MACD 等指標都顯示賣方占主導，短期股價可能繼續承壓。這時候進場像是接刀子，要謹慎。")
    if pv and pv > 2.5:
        bear.append(f"💸 **PEG {pv:.2f}（估值偏高）**\n股價已經反映了非常多的樂觀預期。一旦業績成長低於預期，股價可能大幅回落，風險不小。")
    if de > 100:
        bear.append(f"⚠️ **負債比 {de:.0f}%（高槓桿）**\n公司借了很多錢。在利率高、或景氣不好的時候，利息負擔會壓縮獲利，嚴重時可能有財務危機。")
    if beta > 1.8:
        bear.append(f"🎢 **Beta {beta:.1f}（高波動）**\nBeta 大於 1 代表這支股票的漲跌幅超過大盤。{beta:.1f} 代表大盤跌 10%，這支可能跌 {beta*10:.0f}%。容易因市場情緒影響而大幅震盪。")
    if not bear:
        bear.append("⚪ 目前沒有明顯的負面警示。不過市場隨時可能有意外，建議不要把所有錢都押在單一股票上。")

    # ── 中立客觀 ────────────────────────────────────────────
    fv   = peg.get("fair_value")
    curr = info.get("currentPrice") or info.get("regularMarketPrice")
    neutral = []
    neutral.append(f"📊 **綜合評分**：基本面 {fs}/100、技術面 {ts:+d}分\n基本面 60 分以上算健康，技術面正數代表短期偏多。")
    neutral.append(f"💲 **估值評級**：{peg.get('verdict', '資料不足')}")
    if fv and curr:
        upside = (fv - curr) / curr * 100
        if upside > 0:
            neutral.append(f"📐 **合理估值約 ${fv:.2f}**（現價 ${curr:.2f}）\n根據 PEG 模型，現在還有約 {upside:.0f}% 的上行空間，相對划算。")
        else:
            neutral.append(f"📐 **合理估值約 ${fv:.2f}**（現價 ${curr:.2f}）\n根據 PEG 模型，現價已比合理估值高了 {-upside:.0f}%，代表市場對它的期望已經很高了。")
    neutral.append("⚠️ **投資提醒**\n以上分析基於歷史數據與公式，無法預測未來。建議分批買入（不要一次全下）、單一股票不超過總資金的 10%，並定期檢視是否有新的財報或重大消息。")

    return {"intro": intro, "bull": bull, "bear": bear, "neutral": neutral}


# ════════════════════════════════════════════════════════════
#  MARKET NEWS FEED
# ════════════════════════════════════════════════════════════

def _parse_news_item(item) -> dict:
    """從各種 yfinance 新聞格式中擷取 title/link/ts/pub，回傳 dict 或 {}。"""
    title = link = pub = ""
    ts = 0
    try:
        if isinstance(item, dict):
            # 新格式：{"type":"STORY","content":{...}}
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
            # 舊格式：{"title":"...","link":"...","providerPublishTime":...}
            if not title:
                title = item.get("title") or item.get("headline") or ""
                link  = item.get("link") or item.get("url") or "#"
                ts    = item.get("providerPublishTime") or item.get("publishTime") or 0
                pub_r = item.get("publisher") or item.get("source") or ""
                pub   = pub_r if isinstance(pub_r, str) else (pub_r.get("name","") if isinstance(pub_r,dict) else "")
        else:
            # NewsArticle 物件格式
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

    # --- 方法 A：yfinance .news（美股 + 台股）---
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

    # --- 方法 B：Yahoo Finance RSS（美股）---
    us_count = sum(1 for n in all_news if n["_src"] in set(US_SRC))
    if us_count < 5:
        for sym, src in [("%5EGSPC","^GSPC"),("NVDA","NVDA"),("AAPL","AAPL"),
                          ("TSLA","TSLA"),("MSFT","MSFT"),("META","META"),("AMD","AMD")]:
            _fetch_rss(
                f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US",
                src)

    # --- 方法 C：Yahoo Finance RSS（台股，繁中）---
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
    prompt = f"""以下是今日財經新聞標題，請用繁體中文整理成簡短摘要。

新聞標題：
{headlines_text}

請嚴格按照以下格式輸出，每點不超過25字：

📌 今日重點事件
• （重點1）
• （重點2）
• （重點3）
• （重點4，若有）

📊 整體市場情緒：偏多／偏空／震盪（原因一句話）

⚠️ 值得注意
• （風險或機會1）
• （風險或機會2，若有）

注意：直接輸出內容，不要有任何前言或解釋。繁體中文。"""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2048},
    }
    # 先查詢這個 Key 有哪些可用模型
    try:
        list_r = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=10
        )
        if list_r.status_code != 200:
            return f"[DEBUG] ListModels 失敗 HTTP {list_r.status_code}: {list_r.text[:150]}"
        available = [
            m["name"].replace("models/", "")
            for m in list_r.json().get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        if not available:
            return "[DEBUG] 此 API Key 沒有任何支援 generateContent 的模型"
    except Exception as e:
        return f"[DEBUG] 無法列出模型：{str(e)[:100]}"

    # 優先選 flash 系列（速度快、免費）
    flash = [m for m in available if "flash" in m.lower()]
    model_id = flash[0] if flash else available[0]

    try:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_id}:generateContent?key={api_key}"
        )
        r = requests.post(url, json=payload, timeout=20)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return f"[DEBUG] {model_id} HTTP {r.status_code}: {r.text[:150]}"
    except Exception as e:
        return f"[DEBUG] 呼叫 {model_id} 失敗：{str(e)[:100]}"


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
    st.markdown("## 📈 AI 選股工作站")

    # ── 指數列（緊湊單行）──────────────────────────────────────
    indices = get_indices()
    if indices:
        idx_parts = []
        for idx in indices:
            c = "#3ecf8e" if idx["pct"] >= 0 else "#f07070"
            arrow = "▲" if idx["pct"] >= 0 else "▼"
            idx_parts.append(
                f'<div class="idx-item">'
                f'<span class="idx-name">{idx["name"]}</span>'
                f'<span class="idx-price">{idx["price"]:,.0f}</span>'
                f'<span style="color:{c};font-size:12px;font-weight:700">{arrow}{idx["pct"]:+.2f}%</span>'
                f'</div>'
            )
        st.markdown(
            f'<div class="idx-bar">{"".join(idx_parts)}'
            f'<span style="color:#4a6a88;font-size:11px;margin-left:auto">'
            f'更新 {datetime.now().strftime("%H:%M")}</span></div>',
            unsafe_allow_html=True)
        st.caption(
            "📌 為什麼看這四個指數？"
            "　**S&P 500**＝美國前 500 大企業，是全球最重要的市場溫度計，代表美股整體健康度"
            "　**NASDAQ**＝以科技股為主，AI、半導體、軟體公司為主，波動比 S&P 大但成長性高"
            "　**道瓊**＝美國 30 家最具代表性老牌企業，傳統產業為主，反映美國實體經濟"
            "　**台灣加權**＝台股整體表現，以台積電、鴻海、聯發科等科技業為主力"
        )

    # ── 風控紀律提醒（緊湊版）────────────────────────────────
    st.markdown(
        '<div style="background:#0f1a2e;border:1px solid #2a4a70;border-radius:10px;'
        'padding:10px 16px;margin:8px 0;font-size:12px;color:#8ab8d8;line-height:2">'
        '⚡ <b style="color:#5b9cf6">風控提醒</b>　'
        '💼 單股不超過總資金 <b>10%</b>　'
        '📉 虧損 <b>-8%</b> 停損　'
        '📈 獲利 <b>+30%</b> 先賣一半　'
        '🧘 大跌先看新聞，不恐慌賣出'
        '</div>',
        unsafe_allow_html=True)

    st.markdown("""
<div style="background:linear-gradient(135deg,rgba(91,156,246,.12),rgba(62,207,142,.07));
border:1px solid rgba(91,156,246,.25);border-radius:12px;padding:14px 18px;margin:8px 0 14px">
<div style="color:#cce0ff;font-weight:700;font-size:14px;margin-bottom:6px">
🌱 第一次使用？從這裡開始：
</div>
<div style="color:#7fa8c8;font-size:13px;line-height:1.9">
<b style="color:#cce0ff">① 📰 今日新聞</b>　了解今天市場發生什麼事　→
<b style="color:#cce0ff">② 🌐 主題清單</b>　找你感興趣的產業，看裡面哪支最強　→
<b style="color:#cce0ff">③ 🔍 個股研究</b>　深入研究那支股票　→
<b style="color:#cce0ff">④ 🚨 風險掃雷</b>　買之前確認有沒有隱患
</div>
</div>""", unsafe_allow_html=True)

    tabs = st.tabs([
        "📰 今日新聞","🌐 主題清單","🔍 個股研究","🚨 風險掃雷",
        "📈 買入決策","📉 賣出決策","⚖️ 股票比較","📋 自選股掃描",
        "💼 投資組合","📄 財報解讀","⏳ 長期分析",
    ])

    # ──────────────────────────────────────────────────────
    # TAB 1: 個股研究
    # ──────────────────────────────────────────────────────
    with tabs[2]:
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

            st.markdown("""
<div style="color:#7fa8c8;font-size:12px;border-top:1px solid #1e3050;padding-top:14px;margin-top:4px">
📊 <b style="color:#cce0ff">想深入研究？</b>　下方有技術面、基本面、估值等詳細數字——新手可以先跳過，等對這支股票有興趣後再看。
</div>""", unsafe_allow_html=True)

            t1,t2,t3,t4,t5 = st.tabs(["📊 技術面","📋 基本面","🏷️ 估值","📰 新聞","🏢 公司"])

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
                    TECH_PLAIN = {
                        "MA5 站上 MA20":  "短期均線穿越中期均線往上 → 買氣回升，短線看多",
                        "MA5 跌破 MA20":  "短期均線跌破中期均線 → 買氣減弱，短線看空",
                        "MA20 站上 MA60": "中期均線穿越長期均線往上 → 中期趨勢轉多頭",
                        "MA20 跌破 MA60": "中期均線跌破長期均線 → 中期趨勢轉空頭",
                        "MACD 金叉":      "MACD 線從下方穿越訊號線 → 經典買進訊號",
                        "MACD 死叉":      "MACD 線從上方跌破訊號線 → 經典賣出訊號",
                        "RSI 超買":       "RSI > 70，股價短期漲太快，注意可能回調",
                        "RSI 超賣":       "RSI < 30，股價跌太深，可能醞釀反彈",
                        "RSI 健康":       "RSI 在 30-70 之間，漲跌節奏正常",
                        "觸及布林下軌":   "股價碰到近期低點支撐區，可能出現買盤",
                        "觸及布林上軌":   "股價碰到近期高點壓力區，賣方可能增加",
                        "布林中軌":       "股價在近期平均位置附近，方向不明",
                    }
                    for item in tech["details"]:
                        lbl = item[0]; clr = item[1] if len(item) > 1 else "yellow"
                        icon = "🟢" if clr=="green" else "🔴" if clr=="red" else "🟡"
                        plain = next((v for k,v in TECH_PLAIN.items() if k in lbl), "")
                        st.markdown(f"{icon} **{lbl}**")
                        if plain:
                            st.caption(f"　　{plain}")
                    st.markdown("---")
                    st.markdown(f"**建議進場點**：`${tech['entry']}`　← 現在的市場價格")
                    st.markdown(f"**止損點**：`${tech['stop']}`　← 跌破這個價就該考慮停損出場，控制損失")
                    st.markdown(f"**目標價**：`${tech['target']}`　← 若方向對，預期可到達的價位（風報比約 2:1，賺 2 才賠 1）")

            with t2:
                la, ra = st.columns(2)
                FUND_EXPLAIN = {
                    "ROE":    "ROE（股東權益報酬率）= 公司用你投入的每 1 元能賺回多少。20% 以上非常優秀，代表公司「很會賺錢」。",
                    "毛利率": "毛利率 = 賣出產品後，扣掉直接成本剩下多少比例。越高代表產品競爭力越強、漲價空間越大。50% 以上通常代表有護城河。",
                    "營收年增": "營收年增率 = 跟去年同期相比，收入成長了多少。正數代表生意越做越大，負數代表業績在縮水。",
                    "淨利率": "淨利率 = 所有成本費用都扣完後，最終留下來的獲利比例。越高越好，代表公司不只會賺錢，還很會省錢。",
                    "負債比": "負債比 = 公司借了多少錢（相對於自有資金）。低於 50% 算健康，超過 100% 要小心，利率上升時壓力很大。",
                    "流動比": "流動比 = 公司短期（1年內）的資產 vs 短期負債。超過 2 代表很安全，低於 1 代表可能面臨短期資金壓力。",
                }
                with la:
                    sec("財務指標")
                    for item in fund["details"]:
                        lbl = item[0]; clr = item[1]; desc = item[2] if len(item)>2 else ""
                        icon = "✅" if clr=="green" else "❌" if clr=="red" else "🟡"
                        st.markdown(f"{icon} **{lbl}** — {desc}")
                        explain = next((v for k,v in FUND_EXPLAIN.items() if k in lbl), "")
                        if explain:
                            st.caption(f"　📖 {explain}")
                with ra:
                    sec("公司數據")
                    mc = info.get("marketCap")
                    mc_str = f"${mc/1e9:.1f}B" if mc and mc>1e9 else fmt(mc,",.0f","$")
                    st.metric("市值", mc_str)
                    st.caption("市值 = 公司所有股票的總價值。超過 $10B 算大型股，較穩定；$1B 以下是小型股，波動較大。")
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
    with tabs[7]:
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
            detail_map = {}
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
                    detail_map[t] = {"tc":tc,"fc":fc,"pc":pc,"inf":inf,"sg":sg,"px":px}
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

                # ── 個股詳細理由 ──────────────────────────────
                sec("📋 個股詳細理由（點開看）")
                clr_map = {"green":"#00d896","yellow":"#ffc842","red":"#ff4060"}
                icon_map = {"green":"🟢","yellow":"🟡","red":"🔴"}

                # 白話解釋對照表
                PLAIN = {
                    "ROE":            "= 公司幫股東賺錢的效率，越高代表越會賺錢",
                    "毛利率":          "= 賣出產品扣掉直接成本後剩多少，越高競爭力越強",
                    "營收年增":        "= 跟去年同期比，業績成長了多少",
                    "淨利率":          "= 最終真正留下來的獲利比例，越高越好",
                    "負債比":          "= 公司借了多少錢，越低財務越穩健",
                    "流動比":          "= 短期還得起錢嗎，超過 2 代表很安全",
                    "MA5 站上 MA20":   "→ 短期動能回升，最近股價走強",
                    "MA5 跌破 MA20":   "→ 短期走弱，動能轉差",
                    "MA20 站上 MA60":  "→ 中期趨勢向上確認",
                    "MA20 跌破 MA60":  "→ 中期趨勢轉弱，後市偏空",
                    "MACD 金叉":       "→ 買進技術訊號，多方力量增強",
                    "MACD 死叉":       "→ 賣出技術訊號，空方力量增強",
                    "RSI 超買":        "→ 股價短期漲太多，小心回調",
                    "RSI 超賣":        "→ 股價跌太深，可能即將反彈",
                    "RSI 健康":        "→ 漲跌幅度正常，不極端",
                    "觸及布林下軌":    "→ 股價跌到近期低點，可能有支撐",
                    "觸及布林上軌":    "→ 股價漲到近期高點附近，上方有壓力",
                    "布林中軌":        "→ 股價在近期平均位置附近",
                    "高成長":          "= 業績爆發期，公司正在快速擴張",
                    "穩健":            "= 穩定成長，不算爆發但可持續",
                    "護城河":          "= 產品很難被競爭對手取代，定價權強",
                    "高槓桿":          "= 借了太多錢，利率上升或景氣下滑時壓力大",
                    "財務穩健":        "= 借錢借得少，風險低",
                    "流動性佳":        "= 隨時有錢可以周轉，不怕短期危機",
                    "流動性差":        "= 短期資金緊張，有違約風險",
                }

                def get_plain(label: str) -> str:
                    for key, exp in PLAIN.items():
                        if key in label:
                            return f"　<span style='color:#6b7a99;font-size:12px'>{exp}</span>"
                    return ""

                for t in [r["代碼"] for r in rows]:
                    if t not in detail_map:
                        continue
                    d  = detail_map[t]
                    tc = d["tc"]; fc = d["fc"]; pc = d["pc"]
                    sg = d["sg"]; inf2 = d["inf"]; px = d["px"]
                    name = (inf2.get("shortName","") or t)[:20]
                    sg_color = "#00d896" if "買進" in sg else "#ff4060" if "避開" in sg else "#ffc842"

                    # 產生一句白話結論
                    ts = tc["score"]; fs = fc["score"]; pv = pc.get("peg")
                    why = []
                    if ts >= 40:    why.append("技術面走強")
                    elif ts <= -20: why.append("技術面偏空")
                    else:           why.append("技術面中性")
                    if fs >= 70:    why.append("基本面優良")
                    elif fs >= 50:  why.append("基本面尚可")
                    else:           why.append("基本面偏弱")
                    if pv:
                        if pv < 1:   why.append(f"估值偏低 PEG={pv:.2f}")
                        elif pv > 2: why.append(f"估值偏高 PEG={pv:.2f}")
                    why_str = "、".join(why)

                    with st.expander(f"**{t}** {name}　→　{sg}　｜ {why_str}"):
                        col_t, col_f = st.columns(2)

                        with col_t:
                            st.markdown(f"**📈 技術面　評分 {ts:+d}/100**")
                            for item in tc.get("details", []):
                                lbl = item[0]; clr = item[1] if len(item)>1 else "yellow"
                                ic  = icon_map.get(clr,"🟡")
                                plain = get_plain(lbl)
                                st.markdown(
                                    f'<div style="margin:3px 0">'
                                    f'<span style="color:{clr_map.get(clr,"#ffc842")}">{ic} <b>{lbl}</b></span>'
                                    f'{plain}</div>',
                                    unsafe_allow_html=True)
                            rsi = tc.get("rsi")
                            if rsi:
                                if rsi < 30:
                                    rsi_note = "跌太深，可能快反彈"
                                elif rsi < 45:
                                    rsi_note = "偏低，還有上升空間"
                                elif rsi > 75:
                                    rsi_note = "漲太多，短線小心回調"
                                else:
                                    rsi_note = "正常範圍，不極端"
                                st.caption(f"RSI {rsi:.0f}　— {rsi_note}　（RSI = 衡量股價是否漲／跌過頭的指標，0-100，30以下超賣、70以上超買）")

                        with col_f:
                            st.markdown(f"**💼 基本面　評分 {fs}/100**")
                            for item in fc.get("details", []):
                                lbl = item[0]; clr = item[1] if len(item)>1 else "yellow"
                                desc = item[2] if len(item)>2 else ""
                                ic   = icon_map.get(clr,"🟡")
                                plain = get_plain(lbl)
                                st.markdown(
                                    f'<div style="margin:3px 0">'
                                    f'<span style="color:{clr_map.get(clr,"#ffc842")}">{ic} <b>{lbl}</b>（{desc}）</span>'
                                    f'{plain}</div>',
                                    unsafe_allow_html=True)

                        # 估值
                        st.markdown("**💰 估值（PEG）**")
                        if pv:
                            fv = pc.get("fair_value")
                            v_color = "#00d896" if pv<1.2 else "#ff8c42" if pv<2 else "#ff4060"
                            if pv < 0.8:
                                peg_plain = "股價相對成長速度來說很便宜，是少見的低估機會"
                            elif pv < 1.2:
                                peg_plain = "價格跟公司成長速度匹配，算合理"
                            elif pv < 2:
                                peg_plain = "有點偏貴，需要公司持續維持高成長才撐得住"
                            else:
                                peg_plain = "偏貴，除非公司成長速度超快，否則風險較高"
                            st.markdown(
                                f'PEG <span style="color:{v_color}">**{pv:.2f}**</span>'
                                f'　→　{pc.get("verdict","")}　｜　<span style="color:#6b7a99;font-size:12px">{peg_plain}</span>'
                                + (f'<br><span style="color:#6b7a99;font-size:12px">合理價估算 <b>${fv:.2f}</b>，現價 ${px:.2f}（'
                                   + ("低於合理價，有空間" if px < fv else "高於合理價，已反映成長") + "）</span>" if fv else ""),
                                unsafe_allow_html=True)
                        else:
                            st.caption("PEG 無法計算（缺少本益比或成長率資料）　— PEG 是衡量股價是否合理的指標，越低代表越便宜")

    # ──────────────────────────────────────────────────────
    # TAB 3: 買入決策
    # ──────────────────────────────────────────────────────
    with tabs[4]:
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
    with tabs[5]:
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
    with tabs[6]:
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
    with tabs[3]:
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
            # 風險教學對照表：關鍵字 → (白話解釋, 你該怎麼辦)
            RISK_EDU = {
                "本益比": (
                    "本益比（P/E）= 股價 ÷ 每股盈利。代表你花多少錢買這家公司的「1元獲利」。"
                    "例如本益比 30x，代表你要等 30 年才能靠獲利回本（假設獲利不變）。",
                    "本益比高代表市場對它期望很高，一旦業績不如預期，股價可能大跌。建議搭配成長率看（即 PEG 指標）。"
                ),
                "負債比": (
                    "負債比 = 公司借的錢 ÷ 自己的錢。例如負債比 150% 代表借的錢是自有資金的 1.5 倍。",
                    "公司借太多錢時，利率上升或景氣下滑都可能讓它還不起錢，導致股價暴跌甚至倒閉。建議選負債比 50% 以下的公司。"
                ),
                "營收衰退": (
                    "營收衰退代表這家公司賣出去的東西或服務金額比去年少了，業績在縮水。",
                    "短期衰退有時是暫時的（如季節性），但連續衰退就要警惕。可以去看財報的管理層說明，了解原因。"
                ),
                "空頭": (
                    "空頭佔比（Short Interest）= 做空這支股票的人佔流通股的比例。做空就是「賭它會跌」。",
                    "做空比例高代表很多專業投資人認為這支股票要跌。雖然也可能出現軋空（股價反彈讓做空者虧損），但高空頭是警訊。"
                ),
                "Beta": (
                    "Beta 是衡量股票波動性的指標。Beta=1 代表跟大盤一樣波動；Beta=2 代表大盤跌 10%，它可能跌 20%。",
                    "高 Beta 股票漲的時候漲很多，跌的時候也跌很多。新手建議選 Beta 1.5 以下的股票，比較不容易被嚇到停損。"
                ),
                "52週高點": (
                    "目前股價已接近過去一年的最高點。這個位置上方沒有太多「等著解套的賣壓」，但也代表距離歷史高點很近。",
                    "高點附近需要更多的「業績支撐」才能繼續上漲。如果這時候業績沒有超預期，股價容易回落。建議等回調後再考慮進場。"
                ),
                "MA60": (
                    "MA60（60日均線，也叫季線）是過去 60 個交易日的平均成本。股價跌破季線代表超過一季的持有者都套牢了。",
                    "季線是重要的中期趨勢指標。跌破代表賣壓沉重，通常建議等股價重新站回季線上方後再考慮買入。"
                ),
                "未發現": (
                    "這支股票目前沒有觸發我們設定的主要風險指標。",
                    "但請記住：沒有警示不代表沒有風險，只代表在這些數字面向上看起來相對健康。市場隨時可能有意外消息。"
                ),
            }

            for group, title, border, bg in [
                (hi, "🔴 高風險項目", "#ff4060", "#1a0008"),
                (mi, "🟠 中風險項目", "#ff8c42", "#1a0d00"),
                (lo, "🟢 目前正常",   "#00d896", "#001a0d"),
            ]:
                if group:
                    sec(title)
                    for lbl, _, desc in group:
                        edu = next(((e,a) for k,(e,a) in RISK_EDU.items() if k in lbl), ("",""))
                        st.markdown(
                            f'<div class="card" style="border-left:4px solid {border};background:{bg};padding:14px 18px;margin-bottom:10px">'
                            f'<div style="color:{border};font-weight:700;font-size:15px">⚠ {lbl}</div>'
                            f'<div style="color:#a0b0c0;font-size:13px;margin-top:6px">📋 系統說明：{desc}</div>'
                            + (f'<div style="color:#c8d8e8;font-size:13px;margin-top:8px;padding-top:8px;border-top:1px solid #253040">'
                               f'<b>📖 這是什麼？</b> {edu[0]}</div>'
                               f'<div style="color:#c8d8e8;font-size:13px;margin-top:6px">'
                               f'<b>💡 你應該怎麼做？</b> {edu[1]}</div>' if edu[0] else "")
                            + '</div>',
                            unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────
    # TAB 7: 投資組合
    # ──────────────────────────────────────────────────────
    with tabs[8]:
        sec("💼 投資組合配置建議")
        st.markdown("""
<div class="card" style="border-color:#1e3050">
<div style="color:#5b9cf6;font-weight:700;margin-bottom:8px">💡 為什麼需要「投資組合」？</div>
<div style="color:#8ab8d8;font-size:13px;line-height:1.9">
不把所有錢押在一支股票，是投資最基本的自保原則。<br>
假設你把 100% 的錢買了一支股票，它跌 50%，你就虧了一半。<br>
但如果你分散買了 5 支，就算其中一支腰斬，其他四支可能彌補損失。<br>
<b>這個工具會根據每支股票的基本面與技術面評分，自動幫你計算建議的比例。</b>
</div></div>""", unsafe_allow_html=True)

        col_a, col_b = st.columns([2, 1])
        budget  = col_a.number_input("你有多少錢可以投資？（美元）", 1000, step=500, value=10000, key="pf_b")
        pf_raw  = col_a.text_area("候選股票（每行一個代號）", "AAPL\nMSFT\nNVDA\n2330.TW", height=130, key="pf_t")

        col_b.markdown("<br>", unsafe_allow_html=True)
        col_b.markdown("**選擇你的投資性格：**")
        pf_risk = col_b.radio("", [
            "🚀 成長優先（可以接受大波動，追求高報酬）",
            "⚖️ 均衡（穩健成長，能承受適度波動）",
            "🛡️ 防禦保守（最重要是不要大虧，穩定為主）",
        ], key="pf_r")
        risk_key = "成長優先" if "成長" in pf_risk else "防禦保守" if "防禦" in pf_risk else "均衡"

        if st.button("💡 計算我的最佳配置", type="primary", key="pf_go"):
            pf_tks = [t.strip().upper() for t in pf_raw.split("\n") if t.strip()]
            if len(pf_tks) < 2:
                st.warning("請至少輸入 2 支股票，才能做分散配置")
            else:
                scores = []
                with st.spinner("分析各股票體質中..."):
                    for t in pf_tks:
                        try:
                            inf = get_info(t); dfx = get_price(t, "6mo")
                            fc = fund_score(inf); tc = tech_signal(dfx)
                            beta = inf.get("beta", 1) or 1
                            scores.append({"ticker": t, "name": (inf.get("shortName","") or t)[:14],
                                           "fs": fc["score"], "ts": tc["score"], "beta": beta})
                        except Exception:
                            pass

                wfn = {
                    "成長優先": lambda x: x["fs"]*0.5 + x["ts"]*0.5,
                    "均衡":     lambda x: x["fs"]*0.7 + x["ts"]*0.3,
                    "防禦保守": lambda x: x["fs"]*0.9 - (x["beta"]-1)*10,
                }[risk_key]
                for s in scores: s["w"] = max(0, wfn(s))
                tw = sum(s["w"] for s in scores) or 1
                cash_p = {"成長優先": 5, "均衡": 10, "防禦保守": 20}[risk_key]
                inv_p  = 100 - cash_p

                sec("📊 建議配置結果")
                rows = []
                for s in scores:
                    ap = s["w"] / tw * inv_p
                    amt = budget * ap / 100
                    role = "核心持倉" if ap >= 20 else "衛星持倉" if ap >= 10 else "小倉位觀察"
                    rows.append({
                        "代碼": s["ticker"], "名稱": s["name"],
                        "基本面評分": f"{s['fs']}/100",
                        "技術評分":   f"{s['ts']:+d}",
                        "建議比例":   f"{ap:.1f}%",
                        "建議金額":   f"${amt:,.0f}",
                        "倉位角色":   role,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

                st.markdown(
                    f'<div class="card" style="border-color:#5b9cf6;margin-top:10px">'
                    f'<div style="color:#5b9cf6;font-weight:700">💵 現金部位建議：保留 {cash_p}%　＝　${budget*cash_p/100:,.0f}</div>'
                    f'<div style="color:#8ab8d8;font-size:13px;margin-top:6px">'
                    f'永遠留一部分現金！市場大跌時，現金讓你有機會低價加碼。'
                    f'{"成長型投資者通常留 5%，因為機會成本高。" if risk_key=="成長優先" else "均衡型建議留 10%，當作緩衝和機會資金。" if risk_key=="均衡" else "保守型建議留 20%，確保大跌時心理壓力小、能穩住。"}'
                    f'</div></div>', unsafe_allow_html=True)

                sec("📖 倉位角色說明")
                st.markdown("""
- **核心持倉（≥20%）**：你最有信心的股票，基本面強、長期持有
- **衛星持倉（10-20%）**：補充成長動能的股票，定期檢視
- **小倉位觀察（<10%）**：體質稍弱或波動較大，先小量試水溫，等確認後再加碼

💡 **新手建議**：單一股票不要超過總資金的 20%，就算再看好也一樣。
""")

    # ──────────────────────────────────────────────────────
    # TAB 8: 財報解讀
    # ──────────────────────────────────────────────────────
    with tabs[9]:
        sec("📄 財報快速解讀")
        st.markdown("""
<div class="card" style="border-color:#1e3050">
<div style="color:#5b9cf6;font-weight:700;margin-bottom:8px">📖 什麼是「財報」？為什麼要看它？</div>
<div style="color:#8ab8d8;font-size:13px;line-height:1.9">
財報（財務報告）就是公司的「成績單」，每季公佈一次。<br>
就像學生看分數，投資者看財報來了解：<br>
· 公司賺了多少錢？（收入、利潤）<br>
· 賺錢的能力有沒有變好或變差？（成長率）<br>
· 股價貴不貴？（本益比 P/E）<br>
<b>財報一出來，市場往往大幅波動——這也是最好的加碼或避開時機。</b>
</div></div>""", unsafe_allow_html=True)

        e_t = st.text_input("輸入股票代號", "AAPL", key="et").strip().upper()
        if st.button("📊 解讀財報", type="primary", key="e_go"):
            with st.spinner("載入財報數據..."):
                ei = get_info(e_t); ef = get_financials(e_t)

            name = ei.get("shortName") or e_t
            st.markdown(f"### {name}（{e_t}）財報解讀")

            rev = ei.get("totalRevenue");  rg  = ei.get("revenueGrowth")
            eps = ei.get("trailingEps");   pm  = ei.get("profitMargins")
            gm  = ei.get("grossMargins");  tpe = ei.get("trailingPE"); fpe = ei.get("forwardPE")
            eg  = ei.get("earningsGrowth")

            # ── 收入 ──
            sec("💰 收入（Revenue）—— 公司一年賣出多少？")
            st.markdown("""
<div style="color:#7fa8c8;font-size:12px;margin-bottom:10px">
收入就是公司的「營業額」，代表它向客戶收了多少錢。<br>
收入成長 = 公司業務在擴張；收入衰退 = 警訊，可能失去市場。<br>
<b>成長型科技公司：15%+ 以上才算健康；傳統產業 5%+ 就不錯</b>
</div>""", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            col1.metric("年化總收入", f"${rev/1e9:.1f}B" if rev else "—")
            if rg is not None:
                rg_label = "✅ 強勁成長" if rg > 0.15 else "🟡 溫和成長" if rg > 0 else "🔴 衰退"
                col2.metric("收入年增率", f"{rg*100:+.1f}%", rg_label)
                if rg > 0.20:
                    st.success(f"🚀 收入成長 {rg*100:.0f}%——非常強勁，業務持續擴張中！")
                elif rg > 0.10:
                    st.info(f"✅ 收入成長 {rg*100:.0f}%——健康成長，公司在穩定擴大規模")
                elif rg > 0:
                    st.warning(f"🟡 收入成長 {rg*100:.0f}%——成長放緩，需觀察是否是短期還是趨勢")
                else:
                    st.error(f"🔴 收入衰退 {rg*100:.0f}%——業務萎縮，要查清楚是一次性原因還是結構問題")

            # ── 獲利能力 ──
            sec("📈 獲利能力 —— 公司賺錢的效率")
            st.markdown("""
<div style="color:#7fa8c8;font-size:12px;margin-bottom:10px">
<b>毛利率</b>：賣出商品後，扣掉生產成本，剩下多少比例。越高代表產品越有競爭力、定價能力強。<br>
<b>淨利率</b>：扣掉所有成本（含管銷、稅）後，最終進口袋的比例。這才是「真正賺了多少」。<br>
<b>EPS（每股盈餘）</b>：把公司利潤平分給每一股，代表持有一股能分到多少盈餘。EPS 持續成長是最好的信號。
</div>""", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            gm_pct = gm * 100 if gm else None
            pm_pct = pm * 100 if pm else None
            c1.metric("毛利率", f"{gm_pct:.1f}%" if gm_pct else "—",
                      "優秀 >50%" if gm_pct and gm_pct > 50 else ("良好 >30%" if gm_pct and gm_pct > 30 else "偏低"))
            c2.metric("淨利率", f"{pm_pct:.1f}%" if pm_pct else "—",
                      "優秀 >20%" if pm_pct and pm_pct > 20 else ("還可以 >10%" if pm_pct and pm_pct > 10 else "偏低"))
            c3.metric("每股盈餘 EPS", f"${eps:.2f}" if eps else "—",
                      "正數賺錢✅" if eps and eps > 0 else "虧損中🔴")

            if gm_pct and gm_pct > 50:
                st.success(f"✅ 毛利率 {gm_pct:.0f}%，超過 50%——說明這家公司有很強的定價能力，不容易被競爭對手壓低價格")
            elif gm_pct and gm_pct < 20:
                st.warning(f"🟡 毛利率 {gm_pct:.0f}%，低於 20%——毛利率偏低，公司可能靠薄利多銷，容易受成本上漲影響")

            # ── 估值 ──
            sec("🏷️ 估值 —— 現在股價貴不貴？")
            st.markdown("""
<div style="color:#7fa8c8;font-size:12px;margin-bottom:10px">
<b>本益比 P/E（當前）</b>：股價 ÷ 過去一年每股盈餘。等於「你願意為 1 元利潤付多少錢」。<br>
例：P/E=30 代表你付 30 元，公司每年幫你賺 1 元。P/E 越低通常越便宜（但成長股可以接受高 P/E）。<br>
<b>遠期本益比（Forward P/E）</b>：用「預估未來盈餘」算出的本益比。Forward P/E < 當前 P/E，表示市場預期未來會更賺錢、估值會下降，是好事。
</div>""", unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("當前 P/E", f"{tpe:.1f}x" if tpe else "—")
            c2.metric("遠期 P/E", f"{fpe:.1f}x" if fpe else "—",
                      "估值下降✅" if fpe and tpe and fpe < tpe else "估值上升⚠️" if fpe and tpe else "")
            c3.metric("盈餘成長預估", f"{eg*100:+.1f}%" if eg else "—")

            if tpe and fpe:
                if fpe < tpe * 0.85:
                    st.success(f"✅ 遠期 P/E（{fpe:.1f}x）明顯低於當前 P/E（{tpe:.1f}x）——市場預估公司未來會大幅增長，現在買進相對划算")
                elif fpe > tpe * 1.1:
                    st.warning(f"🟡 遠期 P/E（{fpe:.1f}x）高於當前——市場預期盈餘可能放緩，需謹慎評估")

            # ── 綜合評語 ──
            sec("📝 新手看懂財報：三分鐘總結")
            good, bad = [], []
            if rg and rg > 0.15: good.append("收入強勁成長（+{:.0f}%）".format(rg*100))
            if rg and rg < 0:    bad.append("收入在衰退中（{:.0f}%）".format(rg*100))
            if gm_pct and gm_pct > 40: good.append(f"毛利率高（{gm_pct:.0f}%），有競爭優勢")
            if gm_pct and gm_pct < 20: bad.append(f"毛利率偏低（{gm_pct:.0f}%），成本壓力大")
            if pm_pct and pm_pct > 15: good.append(f"淨利率優秀（{pm_pct:.0f}%），真正賺到很多")
            if pm_pct and pm_pct < 5 and pm_pct > 0: bad.append(f"淨利率偏低（{pm_pct:.0f}%），獲利能力有限")
            if eps and eps < 0:  bad.append("目前虧損（EPS 負數），要確認何時轉虧為盈")
            if fpe and tpe and fpe < tpe: good.append("遠期估值優於當前，市場看好未來成長")
            if eg and eg > 0.15: good.append(f"盈餘成長預估強勁（+{eg*100:.0f}%）")

            if good or bad:
                html_parts = []
                if good:
                    html_parts.append('<div style="color:#3ecf8e;font-weight:700;margin-bottom:6px">✅ 這份財報的亮點</div>')
                    html_parts += [f'<div style="color:#8ab8d8;font-size:13px;margin:2px 0">• {g}</div>' for g in good]
                if bad:
                    html_parts.append('<div style="color:#f07070;font-weight:700;margin:10px 0 6px">⚠️ 這份財報的隱憂</div>')
                    html_parts += [f'<div style="color:#8ab8d8;font-size:13px;margin:2px 0">• {b}</div>' for b in bad]
                st.markdown(f'<div class="card" style="border-color:#1e3050">{"".join(html_parts)}</div>',
                            unsafe_allow_html=True)

            st.markdown("""
<div style="color:#5b9cf6;font-size:12px;margin-top:12px">
💡 <b>新手小提醒</b>：單一財報不能說明一切，要看「趨勢」——連續幾季的收入、EPS 是向上還是向下？
若連續 3 季 EPS 都在成長，那才是真正值得信任的買進信號。
</div>""", unsafe_allow_html=True)

            if ef.get("earnings") is not None:
                try:
                    edf = pd.DataFrame(ef["earnings"])
                    if not edf.empty:
                        sec("📈 歷史 EPS 趨勢")
                        st.caption("EPS 長期向上 = 公司持續賺更多錢，是長期持有的好跡象")
                        st.dataframe(edf.tail(8), use_container_width=True)
                except Exception:
                    pass

    # ──────────────────────────────────────────────────────
    # TAB 9: 長期分析
    # ──────────────────────────────────────────────────────
    with tabs[10]:
        sec("⏳ 長期持有分析")
        st.markdown("""
<div class="card" style="border-color:#1e3050">
<div style="color:#5b9cf6;font-weight:700;margin-bottom:8px">🌱 為什麼「長期持有」是新手最強策略？</div>
<div style="color:#8ab8d8;font-size:13px;line-height:1.9">
巴菲特說：「我最喜歡的持有期限是永遠。」<br>
這不是懶，而是因為複利威力巨大——<br>
· 每年成長 15% 的股票，5 年後變成現在的 2 倍，10 年後是 4 倍，15 年後是 8 倍<br>
· 但短線交易很容易買高賣低，反而賠錢<br>
<b>長期持有的前提：選到體質夠好、有「護城河」的公司</b>
</div></div>""", unsafe_allow_html=True)

        col_l, col_r = st.columns([1, 1])
        lt_t = col_l.text_input("股票代號", "MSFT", key="ltt").strip().upper()
        lt_y = col_r.selectbox("你打算持有多久？", ["5年", "10年", "15年", "20年"], key="lty")

        if st.button("🔭 分析長期投資價值", type="primary", key="lt_go"):
            with st.spinner("深度分析中..."):
                li = get_info(lt_t); ld = get_price(lt_t, "5y")
                lf = fund_score(li); lp = peg_model(li)

            name = li.get("shortName") or lt_t
            st.markdown(f"### {name}（{lt_t}）長期投資分析")

            # ── 護城河評估 ──
            sec("🏰 護城河評估 —— 這家公司憑什麼未來 10 年還能賺錢？")
            st.markdown("""
<div style="color:#7fa8c8;font-size:12px;margin-bottom:10px">
「護城河」就是讓公司維持競爭優勢的能力，就像城堡外的護城河——讓敵人（競爭者）很難攻進來。<br>
沒有護城河的公司，再好的業績也容易被別人模仿或取代。<br>
<b>長期投資一定要選有護城河的公司</b>
</div>""", unsafe_allow_html=True)

            gm  = li.get("grossMargins", 0) or 0
            roe = li.get("returnOnEquity", 0) or 0
            mc  = li.get("marketCap", 0) or 0
            de  = li.get("debtToEquity")
            fcf = li.get("freeCashflow")

            moat_items = []

            if gm > 0.50:
                moat_items.append(("✅", f"高毛利率 {gm*100:.0f}%（超過 50%）",
                    "定價能力超強——這家公司的產品讓人願意付高價，競爭對手很難靠降價搶走它的客戶。如 iPhone、Nike 球鞋都屬於這類。"))
            elif gm > 0.30:
                moat_items.append(("🟡", f"毛利率 {gm*100:.0f}%（30-50%）",
                    "毛利率還不錯，有一定競爭優勢，但護城河不算特別深。"))
            else:
                moat_items.append(("⚠️", f"毛利率 {gm*100:.0f}%（低於 30%）",
                    "毛利率偏低，可能處於激烈競爭市場，長期護城河較弱。"))

            if roe > 0.20:
                moat_items.append(("✅", f"高 ROE {roe*100:.0f}%（超過 20%）",
                    f"ROE 就是「公司幫你的錢賺錢的效率」。{roe*100:.0f}% 代表公司把你投入的每 100 元，賺回 {roe*100:.0f} 元利潤。巴菲特認為持續 ROE > 15% 才算真正的好公司。"))
            elif roe > 0.10:
                moat_items.append(("🟡", f"ROE {roe*100:.0f}%（10-20%）",
                    "ROE 還可以，但稱不上頂尖。觀察是否有持續改善趨勢。"))
            else:
                moat_items.append(("🔴", f"ROE {roe*100:.0f}%（低於 10%）",
                    "資本效率偏低，公司可能面臨激烈競爭或管理效率問題，長期持有需謹慎。"))

            if mc > 500e9:
                moat_items.append(("✅", f"超大型市值（${mc/1e12:.1f}兆）",
                    "規模護城河——市值越大，說明已建立龐大的用戶、品牌和資源。新進競爭者很難在短期內挑戰它的地位。"))
            elif mc > 100e9:
                moat_items.append(("✅", f"大型龍頭（${mc/1e9:.0f}B）",
                    "市場地位穩固，是各產業中的大型玩家，具備一定規模優勢。"))

            if de is not None:
                if de < 30:
                    moat_items.append(("✅", f"極低負債比 {de:.0f}%",
                        f"負債比只有 {de:.0f}%——財務非常健康。市場崩潰時，低負債公司能撐過去，高負債公司可能倒閉。這是長期持有的重要保障。"))
                elif de < 100:
                    moat_items.append(("🟡", f"負債比 {de:.0f}%（尚可）",
                        "負債在可控範圍，但要持續關注，避免負債持續攀升。"))
                else:
                    moat_items.append(("⚠️", f"負債偏高 {de:.0f}%",
                        "公司借了很多錢，利率升高或經濟衰退時壓力大。長期持有前請確認它的還款能力。"))

            if fcf and fcf > 0:
                moat_items.append(("✅", f"正的自由現金流（${fcf/1e9:.1f}B）",
                    "自由現金流 = 公司真正進口袋的現金（非帳面利潤）。現金流充沛的公司，可以不斷投資未來、回購股票、發股息，是長期投資者最愛。"))

            for icon, title, desc in moat_items:
                color = "#3ecf8e" if "✅" in icon else "#f07070" if "🔴" in icon else "#f0b840"
                st.markdown(f"""
<div class="card" style="border-color:{color}33;margin-bottom:8px">
<div style="color:{color};font-weight:700;margin-bottom:4px">{icon} {title}</div>
<div style="color:#8ab8d8;font-size:12px;line-height:1.7">{desc}</div>
</div>""", unsafe_allow_html=True)

            # ── 長期報酬估算 ──
            sec("📊 長期報酬試算 —— 如果現在買，N 年後大概值多少？")
            st.markdown("""
<div style="color:#7fa8c8;font-size:12px;margin-bottom:10px">
這是根據公司目前的成長率，試算未來可能的股價範圍。<br>
<b>注意：這不是保證，只是幫你建立合理預期的參考。</b><br>
實際結果受市場、總體經濟、公司表現等多種因素影響。
</div>""", unsafe_allow_html=True)

            cp  = li.get("currentPrice") or li.get("regularMarketPrice")
            eg  = li.get("earningsGrowth") or li.get("revenueGrowth") or 0.10
            yrs = int(lt_y.replace("年", ""))

            if cp and eg > 0:
                bull  = cp * (1 + eg * 1.3) ** yrs
                base  = cp * (1 + eg * 0.9) ** yrs
                bear  = cp * (1 + max(eg - 0.05, 0.02)) ** yrs

                c1, c2, c3 = st.columns(3)
                c1.metric(f"🐂 樂觀（{yrs}年後）", f"${bull:,.0f}",
                          f"+{(bull/cp-1)*100:.0f}%（假設成長加速）")
                c2.metric(f"📊 基本（{yrs}年後）", f"${base:,.0f}",
                          f"+{(base/cp-1)*100:.0f}%（維持現有速度）")
                c3.metric(f"🐻 悲觀（{yrs}年後）", f"${bear:,.0f}",
                          f"+{(bear/cp-1)*100:.0f}%（成長放緩）")

                st.markdown(f"""
<div class="card" style="border-color:#1e3050;margin-top:10px">
<div style="color:#5b9cf6;font-weight:700;margin-bottom:6px">💡 怎麼看這三個數字？</div>
<div style="color:#8ab8d8;font-size:13px;line-height:1.8">
· 現在股價：<b>${cp:,.2f}</b>　　成長率假設：<b>{eg*100:.1f}% / 年</b>　　持有年數：<b>{yrs} 年</b><br>
· 樂觀情境：公司表現超越預期，成長率加速<br>
· 基本情境：公司維持目前速度，沒有太大意外<br>
· 悲觀情境：成長放緩，但公司還是有穩定發展<br>
<b>就算是悲觀情境，持有 {yrs} 年的預期報酬也是 +{(bear/cp-1)*100:.0f}%——這就是為什麼長期投資很重要！</b>
</div></div>""", unsafe_allow_html=True)

            # ── 何時該停損離開 ──
            sec("🚨 什麼情況下你應該「賣掉」或「重新考慮」？")
            st.markdown("""
<div style="color:#7fa8c8;font-size:12px;margin-bottom:12px">
長期持有不是「買了就不管」——下面這些警訊出現，代表公司的基本面可能在惡化，你需要重新評估。
</div>""", unsafe_allow_html=True)

            THESIS_BREAK = [
                ("🔴", "嚴重警訊", [
                    ("連續 2 季 ROE 低於 10%", "之前說好是賺錢效率高的公司，現在降到 10% 以下——說明護城河可能消失了。行動：研究原因，若是結構性問題就考慮賣出。"),
                    ("毛利率連續下滑超過 5 個百分點", "代表公司在定價能力或成本控制上失去優勢。競爭對手搶市場或原料成本暴漲都可能造成。"),
                    ("核心業務被新技術取代", "比如 Nokia 被智慧手機取代、Kodak 被數位相機打敗。如果公司的主要業務有被取代的風險，要認真考慮。"),
                    ("管理層大換血（CEO/CFO 同時更換）", "管理層是公司的方向盤。同時換掉最高階主管，往往代表公司遇到嚴重問題或內部有矛盾。"),
                ]),
                ("🟡", "黃燈注意", [
                    ("自由現金流連續 3 季下滑", "公司帳面可能有利潤，但真實現金在減少——這是財報開始走壞的早期警訊，密切觀察。"),
                    ("負債比突破 150%", "借款超過自有資金的 1.5 倍，財務壓力大。若加上利率升高，可能出現流動性危機。"),
                    ("市佔率開始下滑", "對手搶走客戶——市佔率一旦開始流失，後面要搶回來非常困難。"),
                ]),
            ]

            for level_color, level_name, signals in THESIS_BREAK:
                color = "#f07070" if "🔴" in level_color else "#f0b840"
                signals_html = "".join([
                    f'<div style="margin:8px 0"><div style="color:{color};font-weight:700;font-size:13px">{level_color} {sig}</div>'
                    f'<div style="color:#8ab8d8;font-size:12px;margin-top:3px;line-height:1.6">{exp}</div></div>'
                    for sig, exp in signals
                ])
                st.markdown(f"""
<div class="card" style="border-color:{color}33;margin-bottom:12px">
<div style="color:{color};font-weight:700;font-size:14px;margin-bottom:8px">{level_color} {level_name}</div>
{signals_html}
</div>""", unsafe_allow_html=True)

            st.markdown("""
<div style="color:#5b9cf6;font-size:12px;margin-top:8px">
💡 <b>原則</b>：出現「黃燈」時先觀察，別急著賣。出現「紅燈」時要認真研究原因——如果確認是結構性問題，果斷停損比繼續持有更明智。
</div>""", unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────
    # TAB 10: 主題清單
    # ──────────────────────────────────────────────────────
    with tabs[1]:
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
    with tabs[0]:
        sec("📰 今日財經新聞")
        st.caption("自動彙整美股大盤、台股、熱門股最新動態，每 30 分鐘更新一次")

        col_filter, col_refresh = st.columns([4,1])
        news_lang = col_filter.radio("篩選",["全部","美股相關","台股相關"],
                                     horizontal=True, key="news_filter")
        if col_refresh.button("🔄 立即更新", key="news_refresh"):
            st.cache_data.clear()

        with st.spinner("載入新聞..."):
            all_news = get_market_news()

        tw_sources = {"^TWII","2330.TW","2317.TW","2454.TW","2308.TW",
                      "2412.TW","2303.TW","3711.TW","0050.TW","2882.TW",
                      "2881.TW","2886.TW","1301.TW","2002.TW","3008.TW"}
        us_sources = {"^GSPC","^IXIC","NVDA","AAPL","META","TSLA","MSFT","AMD","GOOGL","AMZN"}

        if news_lang == "台股相關":
            filtered = [n for n in all_news if n.get("_src") in tw_sources]
        elif news_lang == "美股相關":
            filtered = [n for n in all_news if n.get("_src") in us_sources]
        else:
            filtered = all_news

        st.caption(f"共取得 {len(all_news)} 則新聞，篩選後 {len(filtered)} 則")

        # AI 中文摘要（需要 GEMINI_API_KEY）
        try:
            has_gemini = bool(st.secrets["GEMINI_API_KEY"])
        except Exception:
            has_gemini = False

        if filtered:
            sec("🤖 AI 今日市場摘要")
            if not has_gemini:
                st.caption("尚未設定 GEMINI_API_KEY，請到 Streamlit Cloud → Settings → Secrets 新增")
            else:
                headlines_text = "\n".join(
                    f"[{'台股' if n.get('_src','') in tw_sources else '美股'}] {n['title']}"
                    for n in filtered[:25]
                    if n.get("title","").strip()
                )
                st.caption(f"傳給 AI 的新聞標題：{len(headlines_text.splitlines())} 則")
                if not headlines_text.strip():
                    st.warning("新聞標題是空的，無法生成摘要")
                else:
                    with st.spinner("AI 分析中..."):
                        summary = gemini_news_summary(headlines_text)
                    if summary:
                        st.markdown(
                            f'<div class="card" style="border-color:#9b8cff;padding:16px 20px;line-height:1.8">'
                            f'{summary.replace(chr(10), "<br>")}</div>',
                            unsafe_allow_html=True)
            st.markdown("---")

        if not filtered:
            st.info("暫時沒有新聞，請稍後再試")
        else:
            src_label = {
                "^GSPC":"S&P500","^IXIC":"NASDAQ","^TWII":"台灣加權",
                "NVDA":"NVDA","AAPL":"AAPL","META":"META","TSLA":"TSLA",
                "MSFT":"MSFT","AMD":"AMD","GOOGL":"Google","AMZN":"Amazon",
                "2330.TW":"台積電","2317.TW":"鴻海","2454.TW":"聯發科",
                "2308.TW":"台達電","2412.TW":"中華電","2303.TW":"聯電",
                "3711.TW":"日月光","0050.TW":"元大台灣50","2882.TW":"國泰金",
                "2881.TW":"富邦金","2886.TW":"兆豐金","1301.TW":"台塑",
                "2002.TW":"中鋼","3008.TW":"大立光",
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
