
import json
from collections import Counter
from pathlib import Path

from .agent import Agent
from .generator import save_def
from .judge import judge_case, summarize
from .llm import chat_json
from .prompts import render
from .schemas import AgentAnswer, AgentDef, RuleOut


REASONS = {
    "retrieval_miss": "The expected source document was not among the retrieved chunks.",
    "prompt_defect": "The right context was retrieved but the answer missed or distorted key facts.",
    "hallucination": "The agent made claims not supported by the context, or answered an out-of-scope question.",
    "wrong_refusal": "The agent refused although the retrieved context contained the answer.",
}


def run_evals(defn: AgentDef, cases):
    agent = Agent(defn)
    results = []

    for case in cases:
        try:
            ans, hits = agent.ask(case.question)
        except Exception as e:
            ans, hits = AgentAnswer(
                answer=f"[error] {str(e)[:200]}",
                refused=True
            ), []

        res = judge_case(case, ans, hits)
        results.append(res)

        print(
            f"    {case.id} "
            f"{'PASS' if res.passed else 'FAIL'} "
            f"{res.category or ''}"
        )

    return results


def _add_rule(d: AgentDef, text: str):
    d.system_prompt = (
        d.system_prompt.rstrip()
        + "\nADDITIONAL RULE: "
        + text
    )


def make_candidates(d: AgentDef, category: str, fails):
    """Targeted fixes for ONE category."""

    r, out = d.retrieval, []

    if category == "retrieval_miss":

        if not r.hybrid:
            out.append((
                "enable hybrid search",
                lambda x: setattr(x.retrieval, "hybrid", True)
            ))

        if r.top_k < 10:
            new = min(10, r.top_k + 3)
            out.append((
                f"top_k {r.top_k} -> {new}",
                lambda x, v=new: setattr(x.retrieval, "top_k", v)
            ))

        if r.chunk_words > 150:
            new = r.chunk_words - 100
            out.append((
                f"chunk_words {r.chunk_words} -> {new}",
                lambda x, v=new: setattr(x.retrieval, "chunk_words", v)
            ))

    elif category == "hallucination":

        rules = [
            "Every claim in your answer must be supported by a quote copied exactly from CONTEXT. If you cannot quote supporting evidence, set refused to true.",
            "Never use a number, date, name or amount that does not appear in CONTEXT. If the question is about a topic CONTEXT does not cover, refuse."
        ]

        if d.must_refuse:
            rules.insert(
                1,
                "Always refuse questions about: "
                + "; ".join(d.must_refuse)
                + "."
            )

        out += [
            (f"add rule: {t}", lambda x, t=t: _add_rule(x, t))
            for t in rules
            if t not in d.system_prompt
        ]

    elif category == "wrong_refusal":

        rules = [
            "Only refuse when CONTEXT clearly lacks the information. If CONTEXT contains any relevant passage, answer from it and cite it.",
            "Questions may be phrased casually or vaguely; interpret the likely intent and look for the matching passage in CONTEXT before refusing."
        ]

        out += [
            (f"add rule: {t}", lambda x, t=t: _add_rule(x, t))
            for t in rules
            if t not in d.system_prompt
        ]

    elif category == "prompt_defect":

        ex = "\n\n".join(
            f"Question: {f.question}\nAgent answer: {f.answer[:300]}"
            for f in fails[:3]
        )

        try:
            rule = chat_json(
                "You improve AI system prompts. Reply with JSON only.",
                render("optimizer_rule", examples=ex),
                RuleOut
            ).rule.strip()

        except Exception:
            rule = ""

        if rule and rule not in d.system_prompt:
            out.append((
                f"add rule: {rule}",
                lambda x, t=rule: _add_rule(x, t)
            ))

    return out


def optimize(
    defn: AgentDef,
    cases,
    out_dir,
    max_iter=3,
    min_gain=0.0
):
    out = Path(out_dir)

    (out / "iterations").mkdir(
        parents=True,
        exist_ok=True
    )

    print("  [optimizer] baseline run")

    results = run_evals(defn, cases)
    summary = summarize(results)

    scorecard = [{
        "iteration": 0,
        "change": "baseline (generated agent)",
        "category": "-",
        "score_before": None,
        "score_after": summary["overall"],
        "accepted": True,
        "by_type": summary
    }]

    (out / "iterations" / "iter_0.json").write_text(
        json.dumps({
            "summary": summary,
            "results": [r.model_dump() for r in results]
        }, indent=2),
        encoding="utf-8"
    )

    rejected, logs = set(), []

    for it in range(1, max_iter + 1):

        fails = [
            r for r in results
            if not r.passed
        ]

        if not fails:
            print("  [optimizer] all cases pass, stopping")
            break

        chosen = None

        for cat, _ in Counter(
            r.category for r in fails
        ).most_common():

            cat_fails = [
                r for r in fails
                if r.category == cat
            ]

            for change, fn in make_candidates(
                defn, cat, cat_fails
            ):

                if change not in rejected:
                    chosen = (
                        cat,
                        change,
                        fn,
                        cat_fails
                    )
                    break

            if chosen:
                break

        if not chosen:
            print("  [optimizer] no further targeted fixes available")
            break

        cat, change, fn, cat_fails = chosen

        print(
            f"  [optimizer] iteration {it}: "
            f"{cat} -> {change}"
        )

        cand = defn.model_copy(deep=True)
        fn(cand)

        new_results = run_evals(cand, cases)
        new_sum = summarize(new_results)

        before = summary["overall"]
        after = new_sum["overall"]

        accepted = after > before + min_gain

        was_fail = {
            r.id for r in fails
        }

        now_pass = {
            r.id for r in new_results
            if r.passed
        }

        was_pass = {
            r.id for r in results
            if r.passed
        }

        log = {
            "iteration": it,
            "category": cat,
            "change": change,
            "reason": REASONS[cat],
            "failures_addressed": sorted(was_fail & now_pass),
            "regressions": sorted(was_pass - now_pass),
            "score_before": before,
            "score_after": after,
            "accepted": accepted
        }

        logs.append(log)

        scorecard.append({
            **log,
            "by_type": new_sum
        })

        (out / "iterations" / f"iter_{it}.json").write_text(
            json.dumps({
                **log,
                "results": [
                    r.model_dump()
                    for r in new_results
                ]
            }, indent=2),
            encoding="utf-8"
        )

        if accepted:
            defn, results, summary = (
                cand,
                new_results,
                new_sum
            )

            save_def(
                defn,
                out / "agent" / f"agent_v{it}.yaml"
            )

        else:
            rejected.add(change)
            print("    reverted: score did not improve")

    save_def(
        defn,
        out / "agent" / "agent.yaml"
    )

    (out / "scorecard").mkdir(exist_ok=True)

    (out / "scorecard" / "scorecard.json").write_text(
        json.dumps(scorecard, indent=2),
        encoding="utf-8"
    )

    (out / "scorecard" / "final_results.json").write_text(
        json.dumps([
            r.model_dump()
            for r in results
        ], indent=2),
        encoding="utf-8"
    )

    return defn, results, scorecard, logs
