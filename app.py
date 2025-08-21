
from flask import Flask, render_template, jsonify
import requests, time, traceback
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
import warnings

app = Flask(__name__, static_folder='static', template_folder='templates')

# === Config (embedded) ===
TWELVE_DATA_API_KEY = "b7ea33d435964da0b0a65b1c6a029891"
PAIRS = ["EUR/USD","GBP/USD","USD/JPY","EUR/JPY","AUD/CAD"]
INTERVAL = "5min"
OUTPUTSIZE = 240
TIMEOUT = 15
RETRIES = 2

# === HTTP + Data ===
def http_get_json(url, params, retries=RETRIES, timeout=TIMEOUT):
    last_err = None
    for i in range(retries+1):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:250]}")
        except Exception as e:
            last_err = e
        time.sleep(0.6*(i+1))
    raise last_err

def fetch_candles(pair):
    params = {
        "symbol": pair,
        "interval": INTERVAL,
        "outputsize": OUTPUTSIZE,
        "format": "JSON",
        "apikey": TWELVE_DATA_API_KEY,
    }
    data = http_get_json("https://api.twelvedata.com/time_series", params)
    if isinstance(data, dict) and data.get("status") == "error":
        raise RuntimeError(data.get("message","Twelve Data API error"))
    values = data.get("values") or data.get("data")
    if not values or not isinstance(values, list):
        raise ValueError("No candle 'values' in API response")
    # newest first -> oldest first
    values = list(reversed(values))
    out = []
    for v in values:
        try:
            o = float(v["open"]); h=float(v["high"]); l=float(v["low"]); c=float(v["close"])
            t = v.get("datetime") or v.get("timestamp","")
            if h < max(o,c) or l > min(o,c):  # bad row guard
                continue
            vol = float(v.get("volume", 0) or 0)
            out.append({"t":t,"o":o,"h":h,"l":l,"c":c,"v":vol})
        except Exception:
            continue
    if len(out) < 40:
        raise ValueError("Not enough clean candles")
    return out

# === Heuristic fallback ===
def ema_last(arr, span):
    return pd.Series(arr).ewm(span=span, adjust=False).mean().iloc[-1]

def heuristic_predict(candles):
    try:
        closes = [x["c"] for x in candles]
        e9 = ema_last(closes,9) if len(closes)>=9 else closes[-1]
        e21 = ema_last(closes,21) if len(closes)>=21 else e9
        e50 = ema_last(closes,50) if len(closes)>=50 else e21
        trend = "side"
        if e9>e21>e50: trend="up"
        elif e9<e21<e50: trend="down"
        last = candles[-1]; body = last["c"]-last["o"]
        score = 0.0; why=[]
        if trend=="up": score+=0.8; why.append("EMA up")
        elif trend=="down": score-=0.8; why.append("EMA down")
        else: why.append("sideways")
        if body>0: score+=0.4; why.append("last bullish")
        elif body<0: score-=0.4; why.append("last bearish")
        rng = max(1e-9, last["h"]-last["l"])
        if abs(body)/rng < 0.15: score*=0.7; why.append("small body")
        pred = "CALL" if score>0 else "PUT" if score<0 else "NO_TRADE"
        conf = min(95, max(55, int(50+abs(score)*22)))
        return {"prediction":pred,"confidence":conf,"reason":"; ".join(why),"mode":"heuristic"}
    except Exception as e:
        return {"prediction":"ERROR","confidence":0,"reason":f"Heuristic failed: {e}","mode":"heuristic"}

# === ML ===
def features_df(candles):
    df = pd.DataFrame(candles)
    df["ret"] = df["c"].pct_change().fillna(0.0)
    df["body"] = df["c"]-df["o"]
    df["u_wick"] = df["h"]-df[["c","o"]].max(axis=1)
    df["l_wick"] = df[["c","o"]].min(axis=1)-df["l"]
    df["range"] = (df["h"]-df["l"]).replace(0,np.nan).fillna(method="bfill").fillna(method="ffill")
    df["ema9"] = df["c"].ewm(span=9,adjust=False).mean()
    df["ema21"] = df["c"].ewm(span=21,adjust=False).mean()
    df["ema50"] = df["c"].ewm(span=50,adjust=False).mean()
    df["ema9_21"] = df["ema9"]-df["ema21"]
    df["ema21_50"] = df["ema21"]-df["ema50"]
    df["body_pct_rng"] = (df["body"]/df["range"]).replace([np.inf,-np.inf],0).fillna(0)
    df["vol_ema"] = df["v"].ewm(span=10,adjust=False).mean()
    df = df.replace([np.inf,-np.inf],0).dropna().reset_index(drop=True)
    return df

def train_and_predict(candles):
    try:
        df = features_df(candles)
        # label next candle direction (next close > next open)
        df["next_c"] = df["c"].shift(-1)
        df["next_o"] = df["o"].shift(-1)
        df = df.dropna().reset_index(drop=True)
        df["y"] = (df["next_c"]>df["next_o"]).astype(int)
        feat_cols = ["ret","body","u_wick","l_wick","range","ema9_21","ema21_50","body_pct_rng","v","vol_ema"]
        if len(df) < 60:
            raise ValueError("Insufficient rows for ML")
        X = df[feat_cols].values
        y = df["y"].values
        x_last = df.iloc[-1:][feat_cols].values
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=ConvergenceWarning)
            model = LogisticRegression(solver="liblinear",max_iter=400,class_weight="balanced")
            model.fit(X,y)
        proba = model.predict_proba(x_last)[0]
        p_call = float(proba[1])
        pred = "CALL" if p_call>=0.5 else "PUT"
        conf = int(round(max(p_call,1-p_call)*100))
        return {"prediction":pred,"confidence":conf,"prob_call":round(p_call,4),
                "reason":f"LogReg on {len(y)} samples; features={','.join(feat_cols)}",
                "mode":"ml"}
    except Exception as e:
        fb = heuristic_predict(candles)
        fb["reason"] = f"ML failed: {e} | Fallback -> " + fb.get("reason","")
        fb["mode"] = "ml_fallback"
        return fb

def analyze_pair(pair):
    out = {"pair":pair,"status":"ok"}
    try:
        candles = fetch_candles(pair)
        res = train_and_predict(candles)
        last = candles[-1]
        out.update({
            "prediction":res.get("prediction","ERROR"),
            "confidence":res.get("confidence",0),
            "prob_call":res.get("prob_call"),
            "reason":res.get("reason",""),
            "mode":res.get("mode",""),
            "last_candle":{"t":last["t"],"o":last["o"],"h":last["h"],"l":last["l"],"c":last["c"]}
        })
    except Exception as e:
        out.update({"status":"error","prediction":"ERROR","confidence":0,"reason":f"Pair error: {e}"})
    return out

# === Routes ===
@app.route("/")
def index():
    return render_template("index.html", pairs=PAIRS, interval=INTERVAL)

@app.route("/analyze", methods=["POST"])
def analyze():
    resp = {"status":"ok","results":{}}
    try:
        for p in PAIRS:
            resp["results"][p] = analyze_pair(p)
    except Exception as e:
        resp["status"]="error"
        resp["error"]=str(e)
        resp["trace"]=traceback.format_exc()[:1500]
    return jsonify(resp)

@app.route("/health")
def health():
    return jsonify({"status":"healthy"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
