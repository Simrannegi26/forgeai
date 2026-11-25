import argparse
import json
import time
from pathlib import Path

from .evalgen import generate as gen_evals
from .generator import generate
from .ingest import build_chunks
from .intake import build_requirements, load_brief
from .judge import validate_judge
from .optimizer import optimize
from .report import write_report
from .retrieval import Index
from .schemas import Requirements


def main():
    ap = argparse.ArgumentParser(
        description="ForgeAI: brief + docs -> tested agent"
    )

    ap.add_argument("--brief", required=True)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--auto", action="store_true")
    ap.add_argument("--answers")
    ap.add_argument("--approve", action="store_true")
    ap.add_argument("--max-iter", type=int, default=3)
    ap.add_argument(
        "--stop-after",
        choices=["requirements", "agent", "evals"],
    )

    a = ap.parse_args()

    t0 = time.time()
    brief = load_brief(a.brief)

    Path(a.out).mkdir(parents=True, exist_ok=True)

    print("[1/6] Reading documents")
    chunks = build_chunks(a.docs)

    if not chunks:
        raise SystemExit(
            "No readable text found in the docs folder "
            "(empty or scanned PDFs?)."
        )

    index = Index(chunks)

    print("[2/6] Intake + groundability")
    req = build_requirements(
        brief, index, a.out, a.answers, a.auto
    )

    if a.approve:
        input(
            f"Review/edit {a.out}/requirements/requirements.json, "
            "then press Enter... "
        )

        req = Requirements.model_validate_json(
            Path(
                a.out,
                "requirements",
                "requirements.json",
            ).read_text(encoding="utf-8")
        )

    if a.stop_after == "requirements":
        return

    print("[3/6] Generating agent")
    defn, tool_log = generate(
        req, brief, index, a.docs, a.out
    )

    if a.stop_after == "agent":
        return

    print("[4/6] Generating evals")
    cases = gen_evals(req, index, a.out)

    if a.stop_after == "evals":
        return

    print(
        "[5/6] Evaluate + optimise "
        "(max %d iterations)" % a.max_iter
    )

    defn, results, scorecard, logs = optimize(
        defn, cases, a.out, a.max_iter
    )

    print("[6/6] Judge validation + report")
    jv = validate_judge()

    Path(
        a.out, "scorecard", "judge_validation.json"
    ).write_text(
        json.dumps(jv, indent=2),
        encoding="utf-8",
    )

    write_report(
        a.out,
        brief,
        req,
        defn,
        scorecard,
        results,
        jv,
        tool_log,
        time.time() - t0,
    )


if __name__ == "__main__":
    main()