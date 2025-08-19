from flask import Flask, render_template, jsonify
import requests, os, traceback

app = Flask(__name__)

API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "b7ea33d435964da0b0a65b1c6a029891")
PAIRS = ["EUR/USD", "GBP/USD", "EUR/JPY", "USD/JPY", "AUD/USD"]
INTERVAL = "5min"

def fetch_candles(pair):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval={INTERVAL}&outputsize=10&apikey={API_KEY}"
        r = requests.get(url)
        data = r.json()
        if "values" not in data:
            return None
        candles = []
        for v in reversed(data["values"]):
            candles.append({
                "t": v["datetime"],
                "o": float(v["open"]),
                "h": float(v["high"]),
                "l": float(v["low"]),
                "c": float(v["close"]),
                "v": float(v.get("volume", 0))
            })
        return candles
    except Exception as e:
        print("ERROR fetching:", pair, e)
        return None

def analyze_pair(candles):
    if not candles or len(candles) < 3:
        return {"signal": "NO DATA", "reason": "Not enough candles", "accuracy": 0, "confidence": 0, "last": None}

    last = candles[-1]
    prev = candles[-2]

    # Simple CWRV-like logic using price action + volume
    signal = "PUT" if last["c"] < last["o"] else "CALL"
    reason = "Green candle with higher close" if signal == "CALL" else "Red candle with lower close"

    # Confidence and accuracy placeholders
    confidence = min(100, int(abs(last["c"] - last["o"]) / (last["h"] - last["l"] + 1e-6) * 100))
    accuracy = confidence  # placeholder, can link to history

    return {
        "signal": signal,
        "reason": reason,
        "accuracy": accuracy,
        "confidence": confidence,
        "last": last
    }

@app.route("/")
def index():
    return render_template("index.html", pairs=PAIRS)

@app.route("/analyze")
def analyze():
    results = {}
    for p in PAIRS:
        candles = fetch_candles(p)
        results[p] = analyze_pair(candles)
    return jsonify(results)

@app.route("/debug")
def debug():
    data = {}
    for p in PAIRS:
        data[p] = fetch_candles(p)
    return jsonify(data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
