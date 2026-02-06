import json
from pathlib import Path
from datetime import date

TODAY = date.today().isoformat()

def index_news_sentiment(symbol: str) -> bool:
    sentiment_path = Path(f"data/cleaned/{symbol}/news/sentiment.json")
    index_path = Path(f"data/index/{symbol}.json")

    if not sentiment_path.exists():
        print(f"[{symbol}] sentiment file not found")
        return False

    if not index_path.exists():
        print(f"[{symbol}] index file not found")
        return False

    with open(sentiment_path, "r", encoding="utf-8") as f:
        sentiment = json.load(f)

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)

    index["signals"]["news_sentiment"] = {
        "overall": sentiment["overall_label"],
        "confidence": sentiment["average_confidence"],
        "positive": sentiment["counts"]["positive"],
        "negative": sentiment["counts"]["negative"],
        "neutral": sentiment["counts"]["neutral"],
        "source": str(sentiment_path),
        "last_updated": TODAY
    }


    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"[{symbol}] sentiment indexed")
    return True

if __name__ == "__main__":
    index_news_sentiment("TCS")
    index_news_sentiment("INFY")
