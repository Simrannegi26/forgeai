
import ast
import operator
import re
from datetime import date
from pathlib import Path

import pandas as pd
import requests

REGISTRY = {
    "csv_lookup": "Look up rows (parts, prices, stock, lead times) in the CSV catalogue in the documents folder. Args: {\"query\": \"search words or part number\"}.",
    "calculator": "Evaluate an arithmetic expression such as totals, percentages, discounts. Args: {\"expression\": \"12*45.5*0.95\"}.",
    "weather": "Current weather for a city via the free open-meteo API. Args: {\"city\": \"Rotterdam\"}.",
    "current_date": "Today's date and weekday, for deadlines and expiry. No args.",
}

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > 100:
            raise ValueError("exponent too large")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    raise ValueError("unsupported expression")


def calculator(expression: str) -> str:
    expr = str(expression).replace(",", "").replace("x", "*").replace("%", "/100")
    return f"{expression} = {_eval(ast.parse(expr, mode='eval').body)}"


def csv_lookup(query: str, docs_folder: str) -> str:
    tokens = [t for t in re.findall(r"\w+", str(query).lower()) if len(t) > 2]
    hits = []
    for p in Path(docs_folder).rglob("*.csv"):
        df = pd.read_csv(p).fillna("")
        for _, row in df.iterrows():
            text = " ".join(str(v) for v in row.values).lower()
            score = sum(t in text for t in tokens)
            if score:
                hits.append((score, p.name, row))
    hits.sort(key=lambda h: -h[0])
    if not hits:
        return "No matching rows."
    return "\n".join(
        f"{name}: " + "; ".join(f"{c}: {row[c]}" for c in row.index) for _, name, row in hits[:5]
    )


def weather(city: str) -> str:
    g = requests.get("https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}, timeout=15).json()
    if not g.get("results"):
        return f"City not found: {city}"
    r = g["results"][0]
    w = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": r["latitude"], "longitude": r["longitude"], "current_weather": "true"},
        timeout=15,
    ).json()["current_weather"]
    return f"Weather in {r['name']}: {w['temperature']} C, wind {w['windspeed']} km/h"


def current_date() -> str:
    d = date.today()
    return f"Today is {d.isoformat()} ({d.strftime('%A')})."


def run_tool(name: str, args: dict, docs_folder: str) -> str:
    try:
        if name == "csv_lookup":
            return csv_lookup(args.get("query", ""), docs_folder)
        if name == "calculator":
            return calculator(args.get("expression", ""))
        if name == "weather":
            return weather(args.get("city", ""))
        if name == "current_date":
            return current_date()
        return f"Unknown tool {name}"
    except Exception as e:
        return f"Tool error: {e}"
