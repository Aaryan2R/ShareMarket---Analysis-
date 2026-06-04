import json
from pathlib import Path

RANKING_PATH = Path("data/cleaned/_ranking/today.json")
OUT_DIR = Path("data/cleaned/_ranking")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def normalize_entry(entry):
    """
    Ensures entry is always a dict
    """
    if isinstance(entry, dict):
        return entry
    if isinstance(entry, str):
        return {
            "final_bias": entry,
            "final_score": "NA",
            "trend_strength": "NA",
            "momentum": "NA",
            "volatility": "NA",
        }
    return {}


def explain(company: str, entry: dict) -> str:
    lines = []
    lines.append(f"{company} (Score: {entry.get('final_score', 'NA')})")
    lines.append(f"Bias: {entry.get('final_bias', 'NA')}")
    lines.append(f"Trend strength: {entry.get('trend_strength', 'NA')}")
    lines.append(f"Momentum: {entry.get('momentum', 'NA')}")
    lines.append(f"Volatility risk: {entry.get('volatility', 'NA')}")
    lines.append("")

    score = entry.get("final_score")
    try:
        score = float(score)
    except Exception:
        score = None

    lines.append("Interpretation:")
    if score is None:
        lines.append(
            "Limited structured data available. Use discretionary judgment."
        )
    elif score >= 75:
        lines.append(
            "Strong alignment across trend, momentum, and sentiment. "
            "Suitable for active trades with defined risk."
        )
    elif score >= 55:
        lines.append(
            "Mixed signals detected. Prefer cautious or selective trades."
        )
    else:
        lines.append(
            "Weak or conflicting signals. Avoid aggressive positions."
        )

    return "\n".join(lines)


def run_summary():
    if not RANKING_PATH.exists():
        print("[A6] ranking file not found")
        return

    data = json.loads(RANKING_PATH.read_text(encoding="utf-8"))

    text_blocks = []

    if isinstance(data, dict):
        items = data.items()
    elif isinstance(data, list):
        items = [(d.get("company", "UNKNOWN"), d) for d in data]
    else:
        print("[A6] Unsupported ranking format")
        return

    for i, (company, raw_entry) in enumerate(items, 1):
        entry = normalize_entry(raw_entry)
        text_blocks.append(f"{'='*10} RANK {i} {'='*10}")
        text_blocks.append(explain(company, entry))
        text_blocks.append("")

    OUT_DIR.joinpath("summary.txt").write_text(
        "\n".join(text_blocks), encoding="utf-8"
    )

    print("[A6] trade summary generated")


if __name__ == "__main__":
    run_summary()
