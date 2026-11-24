
import argparse
import json
import re
import sys
from pathlib import Path

from .groundability import apply_groundability
from .ingest import build_chunks, make_profile
from .llm import chat_json
from .prompts import render
from .retrieval import Index
from .schemas import QA, AnswerOut, Questions, ReqDraft, Requirements

SYS = "You are a careful requirements analyst. Reply with JSON only."


def load_brief(arg: str) -> str:
    try:
        p = Path(arg)
        if p.is_file():
            return p.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return arg.strip()


def ask_questions(brief, profile) -> list[str]:
    try:
        out = chat_json(SYS, render("intake_questions", brief=brief, profile=profile), Questions)
        return [q.strip() for q in out.questions if q.strip()][:5]
    except Exception as e:
        print(f"[warn] intake questions failed: {e}")
        return []


def auto_answer(brief, profile, question) -> str:
    try:
        return chat_json(
            SYS,
            render("intake_auto_answer", brief=brief, profile=profile, question=question),
            AnswerOut
        ).answer
    except Exception:
        return "Use conservative defaults."


def collect_answers(questions, brief, profile, answers_path=None, auto=False) -> list[QA]:
    given = []
    if answers_path:
        data = json.loads(Path(answers_path).read_text(encoding="utf-8"))
        given = [str(x) for x in data] if isinstance(data, list) else []

    interactive = (not auto) and (not answers_path) and sys.stdin.isatty()
    qa = []

    for i, q in enumerate(questions):
        if i < len(given):
            qa.append(QA(question=q, answer=given[i], assumed=False))
            continue

        if interactive:
            ans = input(f"\nQ{i+1}. {q}\n> ").strip()
            if ans:
                qa.append(QA(question=q, answer=ans, assumed=False))
                continue

        qa.append(QA(question=q, answer=auto_answer(brief, profile, q), assumed=True))

    return qa


def draft_requirements(brief, profile, qa) -> Requirements:
    qa_text = "\n".join(
        f"Q: {x.question}\nA: {x.answer}" for x in qa
    ) or "(no questions asked)"

    draft = chat_json(
        SYS,
        render("intake_requirements", brief=brief, profile=profile, qa=qa_text),
        ReqDraft
    )

    name = re.sub(r"[^a-z0-9]+", "-", draft.agent_name.lower()).strip("-") or "agent"
    data = draft.model_dump()
    data["agent_name"] = name

    return Requirements(**data, qa=qa)


def write_requirements(req: Requirements, out_dir: str):
    out = Path(out_dir) / "requirements"
    out.mkdir(parents=True, exist_ok=True)

    (out / "requirements.json").write_text(
        req.model_dump_json(indent=2), encoding="utf-8"
    )

    L = [
        f"# Requirements: {req.agent_name}",
        "",
        f"**Scope:** {req.scope}",
        "",
        f"**Audience:** {req.audience}",
        "",
        f"**Tone:** {req.tone}",
        "",
        "## Must answer"
    ]

    L += [f"- {x}" for x in req.must_answer] or ["- (none)"]
    L += ["", "## Must refuse"] + (
        [f"- {x}" for x in req.must_refuse] or ["- (none)"]
    )
    L += ["", "## Gaps (groundability)"] + (
        [f"- {x}" for x in req.gaps] or ["- none found"]
    )
    L += [
        "",
        "## Topic checks",
        "",
        "| Topic | Status | Similarity | LLM | Lexical |",
        "|---|---|---|---|---|"
    ]

    L += [
        f"| {c.topic} | {c.status} | {c.similarity} | {c.llm_yes} | {c.lexical} |"
        for c in req.topic_checks
    ]

    L += ["", "## Intake Q&A"]

    for x in req.qa:
        L.append(
            f"- **Q:** {x.question}\n"
            f"  - **A:** {x.answer}"
            + (" *(assumed)*" if x.assumed else "")
        )

    (out / "requirements.md").write_text("\n".join(L), encoding="utf-8")


def build_requirements(brief, index: Index, out_dir, answers_path=None, auto=False) -> Requirements:
    profile = make_profile(index.chunks)
    questions = ask_questions(brief, profile)
    qa = collect_answers(questions, brief, profile, answers_path, auto)
    req = draft_requirements(brief, profile, qa)
    req = apply_groundability(brief, req, index)
    write_requirements(req, out_dir)
    return req


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", required=True)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--answers")
    ap.add_argument("--auto", action="store_true")
    a = ap.parse_args()

    idx = Index(build_chunks(a.docs))
    r = build_requirements(load_brief(a.brief), idx, a.out, a.answers, a.auto)

    print(f"\nWrote {a.out}/requirements/requirements.md")
    print("Must refuse:", r.must_refuse)
    print("Gaps:", r.gaps)
