
import json
import random
from pathlib import Path

import numpy as np

from .ingest import make_profile
from .groundability import llm_supports
from .llm import chat_json
from .prompts import render
from .schemas import EvalCase, GenQA, OneQuestion, Questions, Requirements
from .textutil import fact_in_strict

SYS = "You create test questions for QA. Reply with JSON only."


def _doc(c):
    return c.get("source", "") if isinstance(c, dict) else c.doc


def _text(c):
    return c.get("text", "") if isinstance(c, dict) else c.text


def usable(c):
    return len(_text(c).split()) >= (
        12 if _doc(c).lower().endswith(".csv") else 40
    )


def round_robin(chunks, rng):
    """Spread chunks evenly across documents, shuffled inside each document."""
    by_doc = {}

    for c in chunks:
        if usable(c):
            by_doc.setdefault(_doc(c), []).append(c)

    for values in by_doc.values():
        rng.shuffle(values)

    order = []
    while any(by_doc.values()):
        for doc in list(by_doc):
            if by_doc[doc]:
                order.append(by_doc[doc].pop())

    return order


def gen_from_chunks(chunks, n, prompt, ctype, subtype, rng):
    cases = []

    for c in round_robin(chunks, rng)[: n * 4]:
        if len(cases) >= n:
            break

        passage = _text(c)

        try:
            g = chat_json(
                SYS,
                render(prompt, passage=passage),
                GenQA
            )
        except Exception:
            continue

        facts = [
            f for f in g.key_facts
            if fact_in_strict(f, passage)
        ]

        if not facts or len(g.question.split()) < 3:
            continue

        cases.append(
            EvalCase(
                type=ctype,
                subtype=subtype,
                question=g.question.strip(),
                expected_refuse=False,
                expected_docs=[_doc(c)],
                key_facts=facts,
                reference_answer=g.answer
            )
        )

    return cases


def gen_multidoc(index, n, rng):
    chunks = index.chunks
    vecs = index.embeddings

    need_diff = len({_doc(c) for c in chunks}) > 1

    order = list(range(len(chunks)))
    rng.shuffle(order)

    cases = []
    used = set()

    for i in order:
        if len(cases) >= n:
            break

        a = chunks[i]

        if not usable(a):
            continue

        partner = None

        for j in np.argsort(-(vecs @ vecs[i])):
            b = chunks[int(j)]

            if (
                int(j) == i
                or (need_diff and _doc(b) == _doc(a))
                or not usable(b)
            ):
                continue

            partner = int(j)
            break

        if partner is None:
            continue

        pair = frozenset((i, partner))

        if pair in used:
            continue

        b = chunks[partner]
        used.add(pair)

        passages = (
            f"PASSAGE A ({_doc(a)}):\n{_text(a)}\n\n"
            f"PASSAGE B ({_doc(b)}):\n{_text(b)}"
        )

        try:
            g = chat_json(
                SYS,
                render("evalgen_multidoc", passages=passages),
                GenQA
            )
        except Exception:
            continue

        fa = [
            f for f in g.key_facts
            if fact_in_strict(f, _text(a))
        ]

        fb = [
            f for f in g.key_facts
            if fact_in_strict(f, _text(b))
        ]

        if not fa or not fb:
            continue

        cases.append(
            EvalCase(
                type="edge",
                subtype="multi_document",
                question=g.question.strip(),
                expected_refuse=False,
                expected_docs=sorted({_doc(a), _doc(b)}),
                key_facts=list(dict.fromkeys(fa + fb)),
                reference_answer=g.answer
            )
        )

    return cases


def gen_oos(req, index, n_total):
    cases = []
    scope = req.scope
    profile = make_profile(index.chunks)

    def add(q, subtype):
        cases.append(
            EvalCase(
                type="out_of_scope",
                subtype=subtype,
                question=q.strip(),
                expected_refuse=True
            )
        )

    for topic in req.must_refuse[:3]:
        try:
            result = chat_json(
                SYS,
                render(
                    "evalgen_topic_question",
                    topic=topic,
                    scope=scope
                ),
                OneQuestion
            )
            add(result.question, "must_refuse")
        except Exception:
            pass

    n_plausible = max(n_total - len(cases) - 2, 2)

    try:
        result = chat_json(
            SYS,
            render(
                "evalgen_oos",
                scope=scope,
                profile=profile,
                n=n_plausible + 2
            ),
            Questions
        )

        for q in result.questions:
            if sum(c.subtype == "plausible" for c in cases) >= n_plausible:
                break

            hits = index.search(q, top_k=3, hybrid=True)

            if not llm_supports(q, hits):
                add(q, "plausible")

    except Exception:
        pass

    try:
        result = chat_json(
            SYS,
            render(
                "evalgen_offtopic",
                scope=scope,
                n=2
            ),
            Questions
        )

        for q in result.questions[:2]:
            add(q, "off_topic")

    except Exception:
        pass

    return cases


def generate(
    req: Requirements,
    index,
    out_dir,
    n_ans=12,
    n_oos=8,
    n_amb=3,
    n_multi=3,
    seed=7
):
    rng = random.Random(seed)

    cases = gen_from_chunks(
        index.chunks,
        n_ans,
        "evalgen_answerable",
        "answerable",
        "single_fact",
        rng
    )

    cases += gen_from_chunks(
        index.chunks,
        n_amb,
        "evalgen_ambiguous",
        "edge",
        "ambiguous_phrasing",
        random.Random(seed + 1)
    )

    cases += gen_multidoc(index, n_multi, rng)
    cases += gen_oos(req, index, n_oos)

    seen = set()
    unique = []

    for c in cases:
        if c.question.lower() not in seen:
            seen.add(c.question.lower())
            unique.append(c)

    for i, c in enumerate(unique, 1):
        c.id = f"c{i:02d}"

    if len(unique) < 20:
        print(
            f"[warn] only {len(unique)} eval cases; "
            "assignment needs at least 20. "
            "Re-run or raise the n_* values."
        )

    path = Path(out_dir) / "evals"
    path.mkdir(parents=True, exist_ok=True)

    (path / "evals.json").write_text(
        json.dumps(
            [c.model_dump() for c in unique],
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"  [evalgen] {len(unique)} cases: "
        + ", ".join(
            f"{t}={sum(c.type == t for c in unique)}"
            for t in ("answerable", "out_of_scope", "edge")
        )
    )

    return unique
