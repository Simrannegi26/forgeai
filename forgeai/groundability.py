
import re

from .llm import chat_json
from .prompts import render
from .schemas import Requirements, TopicCheck, Topics, YesNo

SYS = "You are a careful analyst. Reply with JSON only."
STOP = set(
    "the and for with that this from have has are was were your their about what when which will "
    "into over under they them can could should would policy policies information question questions "
    "staff employees assistant answer answers".split()
)


def lexical_coverage(topic: str, text: str) -> float:
    toks = [t for t in re.findall(r"[a-z0-9]+", topic.lower()) if len(t) > 3 and t not in STOP]
    if not toks:
        return 0.0
    low = text.lower()
    return sum(t[:5] in low for t in toks) / len(toks)


def llm_supports(topic: str, hits) -> bool:
    passages = "\n\n".join(c.text for c, _ in hits)
    try:
        out = chat_json(SYS, render("groundability_check", topic=topic, passages=passages), YesNo)
        return out.answer.strip().lower().startswith("y")
    except Exception:
        return False


def extract_topics(brief: str) -> list[str]:
    try:
        return chat_json(SYS, render("groundability_topics", brief=brief), Topics).topics
    except Exception:
        return []


def check_groundability(brief, req: Requirements, index, sim_threshold: float = 0.5):
    topics = extract_topics(brief)
    seen = {t.lower() for t in topics}
    for t in req.must_answer:
        if t.lower() not in seen:
            topics.append(t)
    checks = []
    for t in topics[:10]:
        hits = index.search(t, top_k=3, hybrid=True)
        sim = max(s for _, s in hits)
        text = " ".join(c.text for c, _ in hits)
        yes = llm_supports(t, hits)
        lex = lexical_coverage(t, text)
        votes = int(yes) + int(sim >= sim_threshold) + int(lex >= 0.5)
        status = "supported" if votes == 3 else "partial" if votes == 2 else "unsupported"
        checks.append(TopicCheck(topic=t, status=status, similarity=round(sim, 3), llm_yes=yes, lexical=round(lex, 2)))
        print(f"  [groundability] {t!r}: {status} (llm={yes}, sim={sim:.2f}, lex={lex:.2f})")
    return checks


def apply_groundability(brief, req: Requirements, index) -> Requirements:
    req.topic_checks = check_groundability(brief, req, index)
    for c in req.topic_checks:
        if c.status == "unsupported":
            if c.topic.lower() not in [m.lower() for m in req.must_refuse]:
                req.must_refuse.append(c.topic)
            req.must_answer = [m for m in req.must_answer if m.lower() != c.topic.lower()]
            req.gaps.append(f"UNSUPPORTED: {c.topic}. No document covers this, so the agent must refuse it.")
        elif c.status == "partial":
            req.gaps.append(f"PARTIAL: {c.topic}. Documents cover this weakly, so answers must be quoted from them.")
    return req
