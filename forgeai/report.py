from pathlib import Path
import yaml

LIMITS = [
    "The eval set is generated from the same documents the agent uses, by a small local model, and the optimizer tuned the agent against that same set. Scores are therefore optimistic; a held-out set would be the next step.",
    "The LLM judge is a small model. Only partially matching answers reach it; its agreement on hand-labelled cases is reported above.",
    "Groundability thresholds (similarity, word overlap) are heuristics calibrated on two demos.",
    "Small-model output varies; results can shift between runs even with fixed seeds.",
]

CAUSE = {
    "retrieval_miss": "expected document not retrieved",
    "prompt_defect": "right context, wrong or incomplete answer",
    "hallucination": "unsupported claim, or answered an out-of-scope question",
    "wrong_refusal": "refused although the answer was in context",
}


def pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


def write_report(
    out_dir,
    brief,
    req,
    defn,
    scorecard,
    final_results,
    judge_val,
    tool_log,
    seconds,
):
    L = [
        f"# ForgeAI Report: {defn.name}",
        "",
        f"**Brief:** {brief}",
        "",
        f"Run time: {seconds / 60:.1f} min",
        "",
        "## Requirements gaps",
    ]

    L += [f"- {g}" for g in req.gaps] or ["- none found"]

    L += [
        "",
        "## Tool selection",
        f"- Kept: {[t['name'] + ' (' + t['justification'] + ')' for t in tool_log['kept']] or 'none'}",
        f"- Dropped by gate: {tool_log['dropped'] or 'none'}",
        "",
        "## Scorecard",
        "",
        "| Iter | Change | Category | Before | After | Accepted |",
        "|---|---|---|---|---|---|",
    ]

    for s in scorecard:
        L.append(
            f"| {s['iteration']} | {s['change']} | {s['category']} | "
            f"{pct(s['score_before'])} | {pct(s['score_after'])} | "
            f"{s['accepted']} |"
        )

    last_ok = [s for s in scorecard if s["accepted"]][-1]["by_type"]

    L += [
        "",
        "## Final scores by case type",
        "",
        f"overall {pct(last_ok['overall'])} (n={last_ok['n']}) | "
        f"answerable {pct(last_ok['answerable'])} | "
        f"out-of-scope {pct(last_ok['out_of_scope'])} | "
        f"edge {pct(last_ok['edge'])}",
        "",
        "## What still fails and why",
        "",
    ]

    fails = [r for r in final_results if not r.passed]

    if fails:
        L += [
            "| Case | Type | Category | Cause | Question | Agent said |",
            "|---|---|---|---|---|---|",
        ]

        for r in fails:
            L.append(
                f"| {r.id} | {r.type} | {r.category} | "
                f"{CAUSE.get(r.category, '')} | {r.question[:80]} | "
                f"{r.answer[:80].replace('|', '/')} |"
            )
    else:
        L.append(
            "No failures on this eval set "
            "(treat with suspicion: see limitations)."
        )

    L += [
        "",
        "## Judge validation",
        "",
        f"Agreement with hand labels: {judge_val['agreement']} on "
        f"{judge_val['n']} cases; negative controls rejected: "
        f"{judge_val['negative_controls_rejected']}; "
        f"judge model: {judge_val['judge_model']}.",
        "",
        "## Final agent definition",
        "",
        "```yaml",
        yaml.safe_dump(
            defn.model_dump(),
            sort_keys=False,
            allow_unicode=True,
        ),
        "```",
        "",
        "## Known limitations",
        "",
    ]

    L += [f"- {x}" for x in LIMITS]

    Path(out_dir, "report.md").write_text(
        "\n".join(L),
        encoding="utf-8",
    )