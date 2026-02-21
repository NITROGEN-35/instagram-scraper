from flask import Flask, render_template, request, jsonify
from scraper import scrape_reel
import pandas as pd
import os

app = Flask(__name__)

CSV_FILE = "reels_data.csv"

if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size == 0:
    df = pd.DataFrame(columns=["Caption", "Likes", "Views", "Comments", "URL"])
    df.to_csv(CSV_FILE, index=False)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.json
    url = data.get("url")

    result = scrape_reel(url)

    if "error" in result:
        return jsonify(result)

    df = pd.read_csv(CSV_FILE)
    df.loc[len(df)] = [
        result["caption"],
        result["likes"],
        result["views"],
        result["comments"],
        result["url"]
    ]
    df.to_csv(CSV_FILE, index=False)

    return jsonify(result)

@app.route("/data")
def get_data():
    df = pd.read_csv(CSV_FILE)
    return df.to_json(orient="records")

if __name__ == "__main__":
    app.run(debug=True)
