import requests
from bs4 import BeautifulSoup
from pathlib import Path
import json

HEADERS = {"User-Agent": "Mozilla/5.0"}

def fetch_ir_reports(symbol: str):
    with open("data/company_ir_map.json", "r", encoding="utf-8") as f:
        ir_map = json.load(f)

    if symbol not in ir_map:
        return

    url = ir_map[symbol]["ir_url"]
    html = requests.get(url, headers=HEADERS, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    links = soup.find_all("a", href=True)
    for a in links:
        href = a["href"]
        text = a.get_text().lower()

        if not href.endswith(".pdf"):
            continue

        if any(k in text for k in ["annual", "integrated", "quarter", "result"]):
            pdf_url = href if href.startswith("http") else url + href
            pdf = requests.get(pdf_url, headers=HEADERS).content

            outdir = Path(f"data/raw/{symbol}/reports/misc")
            outdir.mkdir(parents=True, exist_ok=True)

            fname = pdf_url.split("/")[-1]
            (outdir / fname).write_bytes(pdf)
            print(f"[{symbol}] IR report fetched -> {fname}")
