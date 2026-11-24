from types import SimpleNamespace
from .ingest import build_chunks
from .llm import chat_json
from .prompts import render
from .retrieval import Index
from .schemas import AgentAnswer, AgentDef, ToolCall
from .tools import REGISTRY, run_tool

CONTRACT = """

OUTPUT RULES (strict):
- Answer ONLY using the CONTEXT provided. Never use outside knowledge.
- If the CONTEXT does not contain the answer, set "refused" to true and explain briefly in "answer".
- Reply with ONLY a JSON object with these keys:
  "answer": string,
  "citations": list of {"doc": filename, "quote": short exact quote from CONTEXT},
  "refused": true or false,
  "confidence": number between 0 and 1
"""

_INDEX_CACHE: dict = {}


def get_index(folder, chunk_words, overlap) -> Index:
    key = (folder, chunk_words, overlap)
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = Index(build_chunks(folder, chunk_words, overlap))
    return _INDEX_CACHE[key]


class Agent:
    def __init__(self, definition: AgentDef):
        self.d = definition
        r = definition.retrieval
        self.index = get_index(definition.docs_folder, r.chunk_words, r.overlap)

    def _use_tools(self, question: str) -> list[Chunk]:
        names = [t.name for t in self.d.tools if t.name in REGISTRY]
        if not names:
            return []
        menu = "\n".join(f"- {n}: {REGISTRY[n]}" for n in names)
        try:
            call = chat_json(
                "You route questions to tools. Reply with JSON only.",
                render("tool_router", menu=menu, question=question),
                ToolCall
            )
        except Exception:
            return []
        if not call.tool or call.tool not in names:
            return []
        result = run_tool(call.tool, call.args, self.d.docs_folder)
        return [SimpleNamespace(doc=f"tool:{call.tool}", page=0, text=result)]

    def ask(self, question: str):
        r = self.d.retrieval
        hits = self.index.search(question, r.top_k, r.hybrid)
        hits = [(c, 1.0) for c in self._use_tools(question)] + hits
        context = "\n\n".join(f"[{c.doc} p.{c.page}]\n{c.text}" for c, _ in hits)
        system = self.d.system_prompt + CONTRACT
        user = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
        answer = chat_json(system, user, AgentAnswer)
        return answer, hits
