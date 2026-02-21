# 🚀 InstaReel Analytics Tool

A Flask-based Instagram Reel Data Extractor that collects public reel metrics such as caption, views, likes, and comments using session-based browser automation.

---

## 📌 Overview

InstaReel Analytics is a web-based dashboard that allows users to input a public Instagram Reel URL and extract key engagement metrics in real time.

The project uses:

- Python
- Flask
- Selenium (session-based scraping)
- HTML / CSS / JavaScript
- Git version control

---

## ⚙️ Features

- 🔍 Extract reel caption
- ❤️ Fetch likes count
- 👁 Retrieve view count
- 💬 Extract comments count
- 📊 Display metrics in a clean dashboard UI
- 🕒 Maintain scrape history
- 🔐 Session-based Chrome profile handling
- 📁 Clean project structure with `.gitignore`

---

## 🧠 How It Works

1. User enters a public Instagram Reel URL.
2. Selenium launches Chrome with a session profile.
3. Multiple extraction strategies are applied:
   - GraphQL parsing
   - Embedded JSON extraction
   - DOM fallback parsing
4. Results are merged and displayed in the dashboard.

---

## 🏗 Project Structure

## 🏗 Project Structure


instagram-scraper/
│
├── app.py
├── scraper.py
├── requirements.txt
├── templates/
│ └── index.html
├── static/
│ ├── style.css
│ └── script.js
└── .gitignore


---

## ▶️ How To Run

```bash
pip install -r requirements.txt
python app.py


http://127.0.0.1:5000


⚠️ Disclaimer

This tool is intended for educational and internship demonstration purposes only.
It extracts publicly accessible data and does not bypass authentication systems.
