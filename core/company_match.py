from __future__ import annotations

import re


ALIASES = {
    "tcs": "Tata Consultancy Services",
    "infy": "Infosys",
    "infosys": "Infosys",
    "ril": "Reliance Industries Ltd",
    "reliance": "Reliance Industries Ltd",
    "asian paints": "Asian Paints",
    "asianpaint": "Asian Paints",
}


def abbreviation(name: str) -> str:
    words = [w for w in re.split(r"\s+", name.strip()) if w and w[0].isalpha()]
    return "".join(w[0].lower() for w in words)


def fuzzy_match_one(query: str, companies: list[str]) -> str | None:
    q = query.strip().lower()
    if not q:
        return None

    alias = ALIASES.get(q)
    if alias in companies:
        return alias

    for company in companies:
        if q == company.lower() or q == abbreviation(company):
            return company

    for company in companies:
        cl = company.lower()
        if q in cl or cl in q:
            return company

    tokens = [token for token in re.split(r"\W+", q) if len(token) > 2]
    scored: list[tuple[int, str]] = []
    for company in companies:
        cl = company.lower()
        score = sum(1 for token in tokens if token in cl)
        if score:
            scored.append((score, company))
    return sorted(scored, reverse=True)[0][1] if scored else None


def find_all_mentioned(text: str, companies: list[str]) -> list[str]:
    lower = text.lower()
    found: list[str] = []
    seen: set[str] = set()

    for alias, company in ALIASES.items():
        if company in companies and company not in seen and re.search(r"\b" + re.escape(alias) + r"\b", lower):
            found.append(company)
            seen.add(company)

    for company in companies:
        if company in seen:
            continue
        cl = company.lower()
        abbr = abbreviation(company)
        tokens = [t for t in re.split(r"\W+", cl) if len(t) > 2 and t not in {"ltd", "limited"}]
        if cl in lower or (abbr and re.search(r"\b" + re.escape(abbr) + r"\b", lower)):
            found.append(company)
            seen.add(company)
        elif any(re.search(r"\b" + re.escape(token) + r"\b", lower) for token in tokens):
            found.append(company)
            seen.add(company)
    return found

