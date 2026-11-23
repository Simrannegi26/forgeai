from .ingest import build_chunks
from .llm import chat_json
from .retrieval import Index
from .schemas import AgentAnswer, AgentDef

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


class Agent:
    def __init__(self, definition: AgentDef):
        self.d = definition
        r = definition.retrieval
        chunks = build_chunks(definition.docs_folder, r.chunk_words, r.overlap)
        self.index = Index(chunks)

    def ask(self, question: str):
        r = self.d.retrieval
        hits = self.index.search(question, r.top_k, r.hybrid)
        context = "\n\n".join(f"[{c.doc} p.{c.page}]\n{c.text}" for c, _ in hits)
        system = self.d.system_prompt + CONTRACT
        user = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
        answer = chat_json(system, user, AgentAnswer)
        return answer, hits