import re


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s.lower())).strip()


def numbers(s: str) -> set:
    return set(re.findall(r"\d+(?:\.\d+)?", s.replace(",", "")))


def fact_in_strict(fact: str, text: str) -> bool:
    """Fact must literally appear in text (after normalisation). Used to verify generated evals."""
    nf = norm(fact)
    return bool(nf) and nf in norm(text)


def fact_in(fact: str, text: str) -> bool:
    """Fuzzy: literal match, or numbers all present plus enough word overlap. Used by the judge."""
    nf, nt = norm(fact), norm(text)
    if not nf:
        return False
    if nf in nt:
        return True
    ftoks, ttoks = set(nf.split()), set(nt.split())
    cover = len(ftoks & ttoks) / len(ftoks)
    nums = numbers(fact)
    if nums:
        return nums <= numbers(text) and cover >= 0.5
    return cover >= 0.8