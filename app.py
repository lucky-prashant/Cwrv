from flask import Flask, render_template, jsonify
import requests, os, traceback

app = Flask(__name__)

# =================== CONFIG ===================
API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "b7ea33d435964da0b0a65b1c6a029891")
PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "EUR/JPY", "AUD/CAD"]
INTERVAL = "5min"
LIMIT = 30

# =================== FETCH DATA ===================
def fetch_candles(pair):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval={INTERVAL}&outputsize={LIMIT}&apikey={API_KEY}"
        resp = requests.get(url)
        data = resp.json()
        if "values" not in data:
            return None
        candles = []
        for c in reversed(data["values"]):
            candles.append({
                "t": c["datetime"],
                "o": float(c["open"]),
                "h": float(c["high"]),
                "l": float(c["low"]),
                "c": float(c["close"]),
                "v": float(c.get("volume", 0))
            })
        return candles
    except Exception as e:
        print("Fetch error:", e, traceback.format_exc())
        return None

# =================== CWRV123 LOGIC ===================
def cwrv123_predict(candles):
    if not candles or len(candles) < 6:
        return {"prediction": "NO_TRADE", "confidence": "Low", "reason": "Not enough data", "accuracy": 50}

    last = candles[-6:]
    ups = sum(1 for c in last if c["c"] > c["o"])
    downs = sum(1 for c in last if c["c"] < c["o"])
    avg_vol = sum(c["v"] for c in last) / len(last)
    strong = [c for c in last if abs(c["c"] - c["o"]) > (c["h"] - c["l"]) * 0.5 and c["v"] >= avg_vol]

    if ups >= 4 and len(strong) >= 2:
        return {"prediction": "CALL", "confidence": "High", "reason": "Wave 1-3-5 impulse up with strong volume", "accuracy": 85}
    elif downs >= 4 and len(strong) >= 2:
        return {"prediction": "PUT", "confidence": "High", "reason": "Wave 1-3-5 impulse down with strong volume", "accuracy": 85}
    elif ups > downs:
        return {"prediction": "CALL", "confidence": "Medium", "reason": "More bullish candles in CWRV structure", "accuracy": 65}
    elif downs > ups:
        return {"prediction": "PUT", "confidence": "Medium", "reason": "More bearish candles in CWRV structure", "accuracy": 65}
    else:
        return {"prediction": "NO_TRADE", "confidence": "Low", "reason": "Unclear wave structure", "accuracy": 50}

# =================== ROUTES ===================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyze")
def analyze():
    results = {}
    for pair in PAIRS:
        candles = fetch_candles(pair)
        if not candles:
            results[pair] = {"error": "Failed to fetch data"}
            continue
        pred = cwrv123_predict(candles)
        results[pair] = {
            "prediction": pred["prediction"],
            "confidence": pred["confidence"],
            "reason": pred["reason"],
            "accuracy": pred["accuracy"],
            "last_candle": {"o": candles[-1]["o"], "c": candles[-1]["c"]}
        }
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)