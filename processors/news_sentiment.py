import json
from pathlib import Path
from statistics import mean
from transformers import pipeline

# Finance-tuned sentiment model
sentiment = pipeline(
    "sentiment-analysis",
    model="ProsusAI/finbert"
)

def compute_news_sentiment(symbol: str) -> bool:
    raw_path = Path(f"data/raw/{symbol}/news/latest_news.json")
    if not raw_path.exists():
        print(f"[{symbol}] no raw news found")
        return False

    with open(raw_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    if not items:
        print(f"[{symbol}] empty news list")
        return False

    results = []
    for it in items:
        text = it.get("title", "")
        if not text:
            continue
        r = sentiment(text)[0]
        results.append({
            "title": text,
            "label": r["label"].lower(),
            "score": round(r["score"], 3)
        })

    if not results:
        return False

    labels = [r["label"] for r in results]
    scores = [r["score"] for r in results]

    summary = {
        "overall_label": max(set(labels), key=labels.count),
        "average_confidence": round(mean(scores), 3),
        "counts": {
            "positive": labels.count("positive"),
            "negative": labels.count("negative"),
            "neutral": labels.count("neutral")
        },
        "items": results
    }

    outdir = Path(f"data/cleaned/{symbol}/news")
    outdir.mkdir(parents=True, exist_ok=True)

    outfile = outdir / "sentiment.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[{symbol}] sentiment saved to {outfile}")
    return True
