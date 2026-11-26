"""ForgeAI - minimal Streamlit front end.

Run from the project root:   streamlit run app.py
Reuses the existing backend in forgeai/ (no backend code is duplicated here).
"""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)  # backend uses relative paths (.cache, prompts, tests, docs_folder)
sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
import yaml

from forgeai import agent as agent_mod
from forgeai.agent import Agent
from forgeai.evalgen import generate as gen_evals
from forgeai.generator import generate as gen_agent
from forgeai.groundability import apply_groundability
from forgeai.ingest import build_chunks, make_profile
from forgeai.intake import ask_questions, auto_answer, draft_requirements, write_requirements
from forgeai.judge import validate_judge
from forgeai.llm import JUDGE_MODEL
from forgeai.optimizer import optimize
from forgeai.judge import summarize
from forgeai.optimizer import run_evals
from forgeai.schemas import EvalCase
from forgeai.report import write_report
from forgeai.retrieval import Index
from forgeai.schemas import QA, AgentDef, Requirements

st.set_page_config(page_title="ForgeAI", layout="wide")

DEMOS = ROOT / "demos"
WORK = ROOT / "workspaces"
ALLOWED = (".pdf", ".txt", ".csv", ".md", ".docx")
PAGES = ["Home", "Document Upload", "Agent Creation", "Requirements", "Agent Chat", "Evaluation", "Report"]


# ------------------------------------------------------------------ helpers
class Project:
    """A folder with docs/ plus all generated artifacts (same layout as demos/)."""

    def __init__(self, rel: str):
        self.rel = rel
        self.root = ROOT / rel
        self.docs = self.root / "docs"
        self.docs_rel = f"{rel}/docs"
        self.readonly = rel.startswith("demos/")
        self.name = Path(rel).name
        self.brief = self.root / "brief.txt"
        self.req_json = self.root / "requirements" / "requirements.json"
        self.agent_final = self.root / "agent" / "agent.yaml"
        self.agent_v0 = self.root / "agent" / "agent_v0.yaml"
        self.tool_log = self.root / "agent" / "tool_selection.json"
        self.evals = self.root / "evals" / "evals.json"
        self.scorecard = self.root / "scorecard" / "scorecard.json"
        self.final_results = self.root / "scorecard" / "final_results.json"
        self.judge_val = self.root / "scorecard" / "judge_validation.json"
        self.report = self.root / "report.md"

    def doc_files(self):
        if not self.docs.exists():
            return []
        return sorted(f for f in self.docs.iterdir() if f.is_file() and f.suffix.lower() in ALLOWED)

    def agent_path(self):
        if self.agent_final.exists():
            return self.agent_final
        if self.agent_v0.exists():
            return self.agent_v0
        return None


def list_projects():
    out = []
    for base in (DEMOS, WORK):
        if base.exists():
            for d in sorted(base.iterdir()):
                if d.is_dir() and (d / "docs").exists():
                    out.append(d.relative_to(ROOT).as_posix())
    return out


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def pct(x):
    return "n/a" if x is None else f"{x * 100:.0f}%"


class LiveLog(io.TextIOBase):
    """Shows the backend's print() output live in the page while a long job runs."""

    def __init__(self, box):
        self.box, self.lines, self.buf = box, [], ""

    def write(self, s):
        self.buf += s
        while "\n" in self.buf:
            line, self.buf = self.buf.split("\n", 1)
            if line.strip():
                self.lines.append(line)
        self.box.code("\n".join(self.lines[-18:]) or "working ...")
        return len(s)

    def flush(self):
        pass


def reset_outputs(p: Project, keep_requirements=False):
    names = ["agent", "evals", "iterations", "scorecard"] + ([] if keep_requirements else ["requirements"])
    for d in names:
        shutil.rmtree(p.root / d, ignore_errors=True)
    p.report.unlink(missing_ok=True)


@st.cache_resource(show_spinner=False)
def load_agent(path_str: str, mtime: float):
    with open(path_str, encoding="utf-8") as f:
        return Agent(AgentDef(**yaml.safe_load(f)))


# ------------------------------------------------------------------ pages
def page_home(p):
    st.title("ForgeAI")
    st.subheader("The agent that builds agents")
    st.write(
        "Give ForgeAI a one-paragraph brief and a folder of documents. It interviews you, checks that the "
        "documents can support the request, generates an agent, builds its own test set, judges the agent, "
        "and applies up to 3 targeted fixes. You get the agent, a scorecard and an honest report."
    )
    st.markdown(
        "**Workflow:** 1. Document Upload → 2. Agent Creation → 3. Requirements → 4. Agent Chat → "
        "5. Evaluation → 6. Report"
    )
    if p is None:
        st.info("No project yet. Open **Document Upload** and create one.")
        return
    st.markdown(f"### Active project: `{p.name}`" + ("  (demo, read-only)" if p.readonly else ""))
    rows = [
        ("Documents uploaded", bool(p.doc_files())),
        ("Requirements generated", p.req_json.exists()),
        ("Agent definition generated", p.agent_path() is not None),
        ("Evaluation completed", p.scorecard.exists()),
        ("Report generated", p.report.exists()),
    ]
    for label, ok in rows:
        st.write(("✅ " if ok else "⬜ ") + label)
    if p.readonly:
        st.caption("Demo projects hold the committed artifacts. To run the full factory yourself, create a new "
                   "project on the Document Upload page.")


def page_upload(p):
    st.header("Document Upload")
    with st.expander("Create a new project", expanded=(p is None)):
        name = st.text_input("Project name", placeholder="e.g. hr_test")
        if st.button("Create project"):
            slug = re.sub(r"[^a-z0-9_-]+", "_", name.lower()).strip("_")
            if not slug:
                st.error("Enter a project name (letters and numbers).")
            else:
                (WORK / slug / "docs").mkdir(parents=True, exist_ok=True)
                st.session_state["_set_project"] = f"workspaces/{slug}"
                st.rerun()
    if p is None:
        return
    st.write(f"Project: **{p.name}**")

    if p.readonly:
        st.info("This is a demo project (read-only). Create a new project above to upload your own documents.")
    else:
        files = st.file_uploader("Upload PDF, TXT or CSV files", type=["pdf", "txt", "csv"], accept_multiple_files=True)
        if st.button("Save uploaded files", disabled=not files):
            p.docs.mkdir(parents=True, exist_ok=True)
            for f in files:
                (p.docs / Path(f.name).name).write_bytes(f.getbuffer())
            agent_mod._INDEX_CACHE.clear()
            st.success(f"Saved {len(files)} file(s).")

    existing = p.doc_files()
    st.subheader("Documents in this project")
    if not existing:
        st.caption("No documents yet.")
        return
    counts = Counter(c.get("source", "Unknown") for c in build_chunks(p.docs_rel))
    table = [{"file": f.name, "size_kb": round(f.stat().st_size / 1024, 1), "chunks": counts.get(f.name, 0),
              "status": "OK" if counts.get(f.name, 0) else "No readable text"} for f in existing]
    st.dataframe(pd.DataFrame(table), hide_index=True)
    if any(r["status"] != "OK" for r in table):
        st.warning("Some files have no readable text (empty or scanned PDF). They will be ignored.")
    if not p.readonly:
        victim = st.selectbox("Remove a file", ["-"] + [f.name for f in existing])
        if st.button("Remove selected file", disabled=(victim == "-")):
            (p.docs / victim).unlink(missing_ok=True)
            agent_mod._INDEX_CACHE.clear()
            st.rerun()


def page_create(p):
    st.header("Agent Creation")
    if p is None:
        st.info("Create a project and upload documents first.")
        return
    if not p.doc_files():
        st.warning("This project has no documents. Upload some on the Document Upload page.")
        return
    if p.readonly:
        st.info("Demo project (read-only): showing the committed brief and agent. Create a new project to run "
                "the factory yourself.")
    default = p.brief.read_text(encoding="utf-8") if p.brief.exists() else ""
    brief = st.text_area("Agent brief (one paragraph)", value=default, height=140, disabled=p.readonly,
                         key=f"brief::{p.rel}",
                         placeholder="I need an assistant that answers HR policy questions for shore staff ...")

    if not p.readonly:
        qkey = f"questions::{p.rel}"
        st.markdown("**Step 1.** The intake interviewer reads your brief and documents and asks up to 5 questions.")
        if st.button("Ask clarifying questions", disabled=not brief.strip()):
            chunks = build_chunks(p.docs_rel)
            if not chunks:
                st.error("No readable text found in the documents.")
            else:
                with st.spinner("Reading documents and preparing questions ..."):
                    st.session_state[qkey] = ask_questions(brief.strip(), make_profile(chunks))

        qs = st.session_state.get(qkey)
        if qs is not None:
            st.markdown("**Step 2.** Answer the questions. Leave a box empty and ForgeAI will assume a "
                        "conservative answer (marked *assumed* in the requirements).")
            if not qs:
                st.caption("The interviewer had no questions for this brief.")
            for i, q in enumerate(qs):
                st.text_input(f"Q{i + 1}. {q}", key=f"ans::{p.rel}::{i}")
            if st.button("Generate agent", type="primary"):
                box = st.empty()
                try:
                    with contextlib.redirect_stdout(LiveLog(box)), st.spinner("Generating requirements and agent ..."):
                        reset_outputs(p)
                        p.root.mkdir(parents=True, exist_ok=True)
                        p.brief.write_text(brief.strip(), encoding="utf-8")
                        chunks = build_chunks(p.docs_rel)
                        index = Index(chunks)
                        profile = make_profile(chunks)
                        qa = []
                        for i, q in enumerate(qs):
                            a = st.session_state.get(f"ans::{p.rel}::{i}", "").strip()
                            qa.append(QA(question=q, answer=a, assumed=False) if a
                                      else QA(question=q, answer=auto_answer(brief.strip(), profile, q), assumed=True))
                        req = draft_requirements(brief.strip(), profile, qa)
                        req = apply_groundability(brief.strip(), req, index)
                        write_requirements(req, p.rel)
                        gen_agent(req, brief.strip(), index, p.docs_rel, p.rel)
                    st.success("Agent generated. See the Requirements and Agent Chat pages. "
                               "Run the Evaluation page to test and improve it.")
                except Exception as e:
                    st.error(f"Generation failed: {e}")

    path = p.agent_path()
    if path:
        st.subheader("Generated agent definition")
        log = read_json(p.tool_log, {})
        if log:
            st.write("**Tools kept:** " + (", ".join(f"`{t['name']}` ({t['justification']})" for t in log.get("kept", [])) or "none"))
            if log.get("dropped"):
                st.write("**Tools dropped by the gate:** " + ", ".join(f"`{d['name']}` ({d['reason']})" for d in log["dropped"]))
        st.code(path.read_text(encoding="utf-8"), language="yaml")


def page_requirements(p):
    st.header("Requirements")
    if p is None or not p.req_json.exists():
        st.info("No requirements yet. Generate an agent on the Agent Creation page.")
        return
    req = Requirements.model_validate_json(p.req_json.read_text(encoding="utf-8"))
    c1, c2, c3 = st.columns(3)
    c1.markdown(f"**Scope**\n\n{req.scope}")
    c2.markdown(f"**Audience**\n\n{req.audience}")
    c3.markdown(f"**Tone**\n\n{req.tone}")

    by = {s: [c for c in req.topic_checks if c.status == s] for s in ("supported", "partial", "unsupported")}
    a, b, c = st.columns(3)
    a.success("**Supported topics**\n\n" + ("\n".join(f"- {x.topic}" for x in by["supported"]) or "none"))
    b.warning("**Partially supported**\n\n" + ("\n".join(f"- {x.topic}" for x in by["partial"]) or "none"))
    c.error("**Unsupported (agent must refuse)**\n\n" + ("\n".join(f"- {x.topic}" for x in by["unsupported"]) or "none"))

    l, r = st.columns(2)
    l.markdown("**Must answer**\n\n" + ("\n".join(f"- {x}" for x in req.must_answer) or "- none"))
    r.markdown("**Must refuse**\n\n" + ("\n".join(f"- {x}" for x in req.must_refuse) or "- none"))
    st.markdown("**Gaps (groundability guard)**")
    for g in req.gaps or ["none found"]:
        st.write(f"- {g}")
    if req.topic_checks:
        st.markdown("**Topic check details**")
        st.dataframe(pd.DataFrame([c.model_dump() for c in req.topic_checks]), hide_index=True)
    st.markdown("**Intake Q&A**")
    for x in req.qa:
        st.write(f"- **Q:** {x.question}  \n  **A:** {x.answer}" + ("  *(assumed)*" if x.assumed else ""))
    st.download_button("Download requirements.json", p.req_json.read_text(encoding="utf-8"),
                       file_name="requirements.json", mime="application/json")


def render_msg(m):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            if m.get("refused"):
                st.caption("Refused: the documents do not cover this.")
            if m.get("confidence") is not None:
                st.caption(f"Confidence: {m['confidence']:.2f}")
            cites = m.get("citations", [])
            if cites:
                with st.expander(f"Citations ({len(cites)})"):
                    for c in cites:
                        st.markdown(f"**{c['doc']}**\n\n> {c['quote']}")
            if m.get("retrieved"):
                st.caption("Retrieved: " + ", ".join(m["retrieved"]))


def page_chat(p):
    st.header("Agent Chat")
    path = p.agent_path() if p else None
    if not path:
        st.info("No agent yet. Generate one on the Agent Creation page.")
        return
    st.caption(f"Agent file: `{path.relative_to(ROOT).as_posix()}`")
    with st.spinner("Loading agent (first load builds the index) ..."):
        try:
            agent = load_agent(str(path), path.stat().st_mtime)
        except Exception as e:
            st.error(f"Could not load the agent: {e}")
            return
    st.caption("Tools: " + (", ".join(t.name for t in agent.d.tools) or "none"))
    key = f"chat::{p.rel}"
    hist = st.session_state.setdefault(key, [])
    if st.sidebar.button("Clear chat"):
        st.session_state[key] = hist = []

    q = st.chat_input("Ask your agent a question")
    if q:
        hist.append({"role": "user", "content": q})
        with st.spinner("Thinking ..."):
            try:
                ans, hits = agent.ask(q)
                hist.append({"role": "assistant", "content": ans.answer, "refused": ans.refused,
                             "confidence": ans.confidence, "citations": [c.model_dump() for c in ans.citations],
                             "retrieved": [f"{c.doc} p.{c.page}" for c, _ in hits]})
            except Exception as e:
                hist.append({"role": "assistant", "content": f"Error: {e}"})
    for m in hist:
        render_msg(m)


def run_evaluation(p: Project, iters: int):
    t0 = time.time()
    req = Requirements.model_validate_json(p.req_json.read_text(encoding="utf-8"))
    brief = p.brief.read_text(encoding="utf-8") if p.brief.exists() else ""
    tool_log = read_json(p.tool_log, {"kept": [], "dropped": []})
    with open(p.agent_v0, encoding="utf-8") as f:
        defn = AgentDef(**yaml.safe_load(f))
    for d in ("evals", "iterations", "scorecard"):
        shutil.rmtree(p.root / d, ignore_errors=True)
    p.report.unlink(missing_ok=True)
    box = st.empty()
    with contextlib.redirect_stdout(LiveLog(box)):
        index = Index(build_chunks(p.docs_rel))
        cases = gen_evals(req, index, p.rel)
        if not cases:
            raise RuntimeError("No eval cases could be generated from these documents.")
        defn, results, scorecard, _ = optimize(defn, cases, p.rel, iters)
        try:
            jv = validate_judge()
        except Exception as e:
            jv = {"agreement": 0.0, "n": 0, "negative_controls_rejected": "0/0", "judge_model": JUDGE_MODEL,
                  "detail": [], "error": str(e)}
        (p.root / "scorecard" / "judge_validation.json").write_text(json.dumps(jv, indent=2), encoding="utf-8")
        write_report(p.rel, brief, req, defn, scorecard, results, jv, tool_log, time.time() - t0)
    return len(cases)

def run_fixed_evaluation(p: Project):
    agent_file = p.agent_final
    eval_file = p.evals

    if not agent_file.exists():
        raise FileNotFoundError(f"Agent not found: {agent_file}")

    if not eval_file.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {eval_file}")

    definition = AgentDef(
        **yaml.safe_load(agent_file.read_text(encoding="utf-8"))
    )

    cases = [
        EvalCase(**item)
        for item in json.loads(eval_file.read_text(encoding="utf-8"))
    ]

    box = st.empty()

    with contextlib.redirect_stdout(LiveLog(box)):
        results = run_evals(definition, cases)
        summary = summarize(results)

    out = p.root / "scorecard"
    out.mkdir(parents=True, exist_ok=True)

    result_path = out / "eval_only_streamlit.json"
    result_path.write_text(
        json.dumps([r.model_dump() for r in results], indent=2),
        encoding="utf-8"
    )

    summary_path = out / "eval_only_streamlit_summary.json"
    summary_path.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8"
    )

    return summary



def page_eval(p):
    st.header("Evaluation")

    if p is None or not p.agent_final.exists() or not p.evals.exists():
        st.info("The final agent and existing evaluation dataset are required.")
        return

    st.subheader("Fixed Dataset Evaluation")
    st.write(
        "Evaluates the existing agent.yaml against the existing evals.json. "
        "Does not regenerate test cases or run optimization."
    )

    if st.button("Evaluate Existing Agent", type="primary"):
        try:
            with st.spinner("Evaluating existing test cases..."):
                summary = run_fixed_evaluation(p)
            st.success("Fixed evaluation completed.")
            st.json(summary)
        except Exception as e:
            st.error(f"Evaluation failed: {e}")

    st.divider()

    st.subheader("Full Evaluation and Optimization")
    if not p.readonly:
        st.write(
            "Generates a new evaluation dataset and runs the optimization workflow."
        )
        iters = st.slider(
            "Maximum optimisation iterations", 1, 3, 3
        )

        if st.button("Run evaluation and optimisation"):
            try:
                with st.spinner("Running evaluation and optimisation..."):
                    n = run_evaluation(p, iters)
                st.success(f"Finished. {n} test cases generated.")
            except Exception as e:
                st.error(f"Evaluation failed: {e}")
    else:
        st.caption("Optimization is disabled for read-only demo projects.")


def page_report(p):
    st.header("Report")
    if p is None or not p.report.exists():
        st.info("No report yet. Run the Evaluation page first.")
        return
    text = p.report.read_text(encoding="utf-8")
    c1, c2, _ = st.columns([1, 1, 3])
    c1.download_button("Download report.md", text, file_name=f"{p.name}_report.md", mime="text/markdown")
    path = p.agent_path()
    if path:
        c2.download_button("Download agent.yaml", path.read_text(encoding="utf-8"),
                           file_name=f"{p.name}_agent.yaml", mime="text/yaml")
    st.divider()
    st.markdown(text)


# ------------------------------------------------------------------ main
if "_set_project" in st.session_state:  # set before the sidebar widget is created
    st.session_state["project"] = st.session_state.pop("_set_project")

projects = list_projects()
st.sidebar.title("ForgeAI")
page = st.sidebar.radio("Navigate", PAGES)
if st.session_state.get("project") not in projects:
    st.session_state.pop("project", None)
current = None
if projects:
    choice = st.sidebar.selectbox(
        "Active project", projects, key="project",
        format_func=lambda r: Path(r).name + ("  (demo, read-only)" if r.startswith("demos/") else ""))
    current = Project(choice)
else:
    st.sidebar.caption("No projects yet.")

{"Home": page_home, "Document Upload": page_upload, "Agent Creation": page_create,
 "Requirements": page_requirements, "Agent Chat": page_chat, "Evaluation": page_eval,
 "Report": page_report}[page](current)