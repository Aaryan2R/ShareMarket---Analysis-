# run_diagnostics.py
import json, os, traceback
from pathlib import Path
from ai_trading_assistant_ui import list_raw_dirs, find_csv_for_company, read_price_df, get_companies, validate_company_data, compute_positive_close_rate, plot_interactive_plotly, PLOTLY_AVAILABLE, fetch_news_rss

ROOT = Path(".")
DIAG_DIR = ROOT / "diagnostics"
DIAG_DIR.mkdir(parents=True, exist_ok=True)
out = {"timestamp": __import__("datetime").datetime.now().isoformat(), "results": []}

companies = get_companies()
if not companies:
    print("No companies in RAG dataset (check data/cleaned/_daily_intelligence.json).")
companies_to_test = companies or []

# 1) List CSVs
csv_listing = {}
for d in list_raw_dirs():
    csv_listing[d] = []
    # find csvs
    p = ROOT / "data" / "raw" / d
    for f in p.rglob("*.csv"):
        csv_listing[d].append(str(f))
out["csv_listing"] = csv_listing

# tests per company
for comp in companies_to_test:
    try:
        entry = {"company": comp}
        p, searched = find_csv_for_company(comp)
        entry["found_csv"] = str(p) if p else None
        entry["searched_samples"] = searched[:20]
        df_searched = read_price_df(comp)[0]
        entry["df_present"] = df_searched is not None
        # validate
        entry["validation"] = validate_company_data(comp)
        # compute win rate 30
        entry["win_rate_30"] = compute_positive_close_rate(comp, days=30)
        # try to create interactive plot html (if plotly available)
        if PLOTLY_AVAILABLE and df_searched is not None:
            try:
                html_path = plot_interactive_plotly(df_searched, comp, "Date", "Close", out_html_path=DIAG_DIR / f"{comp.replace(' ','_')}_diag_chart.html")
                entry["chart_html"] = html_path
            except Exception as e:
                entry["chart_error"] = str(e)
        out["results"].append(entry)
    except Exception as e:
        out["results"].append({"company": comp, "error": str(e), "trace": traceback.format_exc()})

# optional: fetch news for first company (opt-in)
if companies_to_test:
    comp0 = companies_to_test[0]
    try:
        nres = fetch_news_rss(comp0, days=1)
        out["news_fetch"] = nres
    except Exception as e:
        out["news_fetch_error"] = str(e)

# write diagnostics
with open(DIAG_DIR / "diagnostics.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)

print("Diagnostics complete ->", DIAG_DIR / "diagnostics.json")