
import json
import re
from pathlib import Path

from .llm import JUDGE_MODEL, chat_json
from .prompts import render
from .schemas import AgentAnswer, CaseResult, EvalCase, YesNo
from .textutil import fact_in, norm


REFUSE_RE = re.compile(
    r"(cannot|can't|can not|unable to) (answer|help|provide|find)|not (mentioned|covered|specified|available|found)"
    r"|no (information|mention)|(don't|do not) have (information|enough)|outside (the|my) scope",
    re.I,
)


def llm_correct(case: EvalCase, answer_text: str) -> bool:
    ref = "Key facts: " + "; ".join(case.key_facts)
    verdicts = []

    for swap in (False, True):
        blocks = [("REFERENCE", ref), ("CANDIDATE", answer_text)]

        if swap:
            blocks.reverse()

        text = "\n\n".join(f"{k}:\n{v}" for k, v in blocks)

        try:
            out = chat_json(
                "You are a strict grader. Reply with JSON only.",
                render("judge", question=case.question, blocks=text),
                YesNo,
                model=JUDGE_MODEL,
            )
            verdicts.append(out.answer.strip().lower().startswith("y"))

        except Exception:
            verdicts.append(False)

    # Both swapped-order evaluations must agree.
    return all(verdicts)


def is_correct(case: EvalCase, answer_text: str):
    matched = [fact_in(f, answer_text) for f in case.key_facts]

    if matched and all(matched):
        return True, "deterministic"

    if not any(matched):
        return False, "deterministic"

    return llm_correct(case, answer_text), "llm"


def quote_supported(quote: str, context: str) -> bool:
    nq, nc = norm(quote), norm(context)

    if not nq:
        return False

    if nq in nc:
        return True

    toks = nq.split()
    ctoks = set(nc.split())

    return sum(t in ctoks for t in toks) / len(toks) >= 0.85


def is_grounded(case: EvalCase, ans: AgentAnswer, context: str) -> bool:
    cites = ans.citations

    if not cites:
        return False

    if not all(quote_supported(c.quote, context) for c in cites):
        return False

    if not case.expected_docs:
        return True

    return (
        any(e in c.doc for e in case.expected_docs for c in cites)
        or any(c.doc.startswith("tool:") for c in cites)
    )


def classify(case: EvalCase, res: CaseResult):
    if res.passed:
        return None

    if case.expected_refuse:
        return "hallucination"

    missing = (
        bool(case.expected_docs)
        and not set(case.expected_docs) <= set(res.retrieved_docs)
    )

    if missing:
        return "retrieval_miss"

    if res.refused:
        return "wrong_refusal"

    if res.grounded is False:
        return "hallucination"

    return "prompt_defect"


def judge_case(case: EvalCase, ans: AgentAnswer, hits) -> CaseResult:
    context = "\n".join(c.text for c, _ in hits)

    refused = ans.refused or bool(REFUSE_RE.search(ans.answer[:200]))

    res = CaseResult(
        id=case.id,
        type=case.type,
        question=case.question,
        expected_refuse=case.expected_refuse,
        answer=ans.answer,
        refused=refused,
        citations=ans.citations,
        retrieved_docs=sorted({c.doc for c, _ in hits}),
        refusal_ok=(refused == case.expected_refuse),
    )

    if case.expected_refuse:
        res.passed = res.refusal_ok

    elif not refused:
        res.correct, res.method = is_correct(case, ans.answer)
        res.grounded = is_grounded(case, ans, context)
        res.passed = bool(res.correct and res.grounded)

    else:
        res.correct = False

    res.category = classify(case, res)

    return res


def summarize(results) -> dict:
    def rate(rs):
        return (
            round(sum(r.passed for r in rs) / len(rs), 3)
            if rs else None
        )

    summary = {
        "overall": rate(results),
        "n": len(results),
    }

    for case_type in ("answerable", "out_of_scope", "edge"):
        summary[case_type] = rate(
            [r for r in results if r.type == case_type]
        )

    return summary


def validate_judge(labels_path="tests/judge_labels.json") -> dict:
    """Evaluate the judge against hand-labelled examples."""

    items = json.loads(
        Path(labels_path).read_text(encoding="utf-8")
    )

    agree = 0
    neg_total = 0
    neg_ok = 0
    detail = []

    for item in items:
        case = EvalCase(
            id="x",
            type="answerable",
            question=item["question"],
            expected_refuse=False,
            key_facts=item["key_facts"],
        )

        pred, method = is_correct(case, item["candidate"])
        ok = pred == item["label"]

        agree += ok

        if item.get("negative_control"):
            neg_total += 1
            neg_ok += pred is False

        detail.append({
            "candidate": item["candidate"],
            "label": item["label"],
            "predicted": pred,
            "method": method,
            "agree": ok,
        })

    return {
        "agreement": round(agree / len(items), 2) if items else None,
        "n": len(items),
        "negative_controls_rejected": f"{neg_ok}/{neg_total}",
        "judge_model": JUDGE_MODEL,
        "detail": detail,
    }
