import json
from pathlib import Path

import yaml

from .llm import chat_json
from .prompts import render
from .schemas import AgentDef, PromptOut, Requirements, Retrieval, ToolProposal
from .tools import REGISTRY
from .tools.gate import gate

SYS = "You are an expert AI agent designer. Reply with JSON only."


def save_def(defn: AgentDef, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        yaml.safe_dump(
            defn.model_dump(),
            sort_keys=False,
            allow_unicode=True
        ),
        encoding="utf-8"
    )


def pick_retrieval(chunks) -> Retrieval:
    has_csv = any(
        (c.get("source", "") if isinstance(c, dict) else c.doc).lower().endswith(".csv")
        for c in chunks
    )
    return Retrieval(
        chunk_words=300,
        overlap=50,
        top_k=6 if has_csv else 4,
        hybrid=True
    )


def generate(req: Requirements, brief: str, index, docs_folder: str, out_dir: str):
    chunks = index.chunks

    # 1. LLM proposes tools
    proposal = ToolProposal()
    try:
        menu = "\n".join(f"- {k}: {v}" for k, v in REGISTRY.items())
        files = ", ".join(sorted({
    c.get("source", "") if isinstance(c, dict) else c.doc
    for c in chunks
}))

        proposal = chat_json(
            SYS,
            render(
                "generator_tools",
                brief=brief,
                scope=req.scope,
                must_answer="; ".join(req.must_answer),
                files=files,
                menu=menu
            ),
            ToolProposal
        )
    except Exception as e:
        print(f"[warn] tool proposal failed ({e}); attaching no tools")

    # 2. Deterministic gate
    gate_text = " ".join([brief, req.scope] + req.must_answer)
    kept, dropped = gate(proposal.tools, gate_text, docs_folder)

    tool_log = {
        "proposed": [t.model_dump() for t in proposal.tools],
        "kept": [t.model_dump() for t in kept],
        "dropped": dropped
    }

    # 3. Generate system prompt
    try:
        sp = chat_json(
            SYS,
            render(
                "generator_system",
                scope=req.scope,
                audience=req.audience,
                tone=req.tone,
                must_answer="; ".join(req.must_answer) or "-",
                must_refuse="; ".join(req.must_refuse) or "-"
            ),
            PromptOut
        ).system_prompt.strip()
    except Exception:
        sp = (
            f"You are {req.agent_name}, an assistant for {req.audience}. "
            f"Scope: {req.scope}. Tone: {req.tone}."
        )

    if req.must_refuse:
        sp += "\n\nYou must refuse questions about: " + "; ".join(req.must_refuse) + "."

    partial = [
        c.topic for c in req.topic_checks
        if c.status == "partial"
    ]

    if partial:
        sp += (
            "\nDocument coverage is weak for: "
            + "; ".join(partial)
            + ". Answer only with quoted evidence, otherwise refuse."
        )

    defn = AgentDef(
        name=req.agent_name,
        docs_folder=docs_folder,
        system_prompt=sp,
        retrieval=pick_retrieval(chunks),
        tools=kept,
        must_refuse=req.must_refuse
    )

    save_def(defn, Path(out_dir) / "agent" / "agent_v0.yaml")

    (
        Path(out_dir) / "agent" / "tool_selection.json"
    ).write_text(
        json.dumps(tool_log, indent=2),
        encoding="utf-8"
    )

    print(
        f"  [generator] tools kept: "
        f"{[t.name for t in kept]}  dropped: {dropped}"
    )

    return defn, tool_log