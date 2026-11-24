
import re
from pathlib import Path

from . import REGISTRY

KEYWORDS = {
    "weather": ["weather", "forecast", "rain", "storm", "temperature", "wind", "climate"],
    "current_date": ["deadline", "today", "due date", "expir", "overdue", "upcoming", "days left",
                     "days remaining", "current date", "how long until"],
    "calculator": ["calculat", "total", "cost", "price", "budget", "quote", "sum", "convert",
                   "percentage", "discount", "estimate", "compute", "how much"],
}


def gate(proposed, text: str, docs_folder: str):
    """Returns (kept, dropped). dropped is a list of {name, reason}."""
    kept, dropped, seen = [], [], set()
    text = text.lower()
    has_csv = any(Path(docs_folder).rglob("*.csv"))
    for t in proposed:
        reason = None
        if t.name in seen:
            reason = "duplicate"
        elif t.name not in REGISTRY:
            reason = "not in registry"
        elif len(t.justification.strip()) < 10:
            reason = "missing justification"
        elif t.name == "csv_lookup" and not has_csv:
            reason = "no CSV file in the documents"
        elif t.name in KEYWORDS and not re.search(r"\b(" + "|".join(KEYWORDS[t.name]) + ")", text):
            reason = "brief never mentions anything that needs this tool"
        if reason:
            dropped.append({"name": t.name, "reason": reason})
        else:
            kept.append(t)
            seen.add(t.name)
    return kept, dropped
