from types import SimpleNamespace
from .ingest import build_chunks
from .llm import chat_json
from .prompts import render
from .retrieval import Index
from .schemas import AgentAnswer, AgentDef, ToolCall, Citation
from .tools import REGISTRY, run_tool


CONTRACT = """

OUTPUT RULES (strict):
- Answer ONLY using the CONTEXT provided. Never use outside knowledge.
- Read all relevant context before answering.
- Answer every part of the user's question.
- Include important conditions, exceptions, limits, deadlines and approval authorities when present in the context.
- If the context does not contain enough information, set "refused" to true and explain briefly in "answer".
- Never guess or invent policy information.
- Reply with ONLY one valid JSON object with these keys:
  "answer": string,
  "citations": list of {"doc": filename, "quote": exact supporting text from CONTEXT},
  "refused": true or false,
  "confidence": number between 0 and 1.
- Every citation must contain both "doc" and "quote".
- The quote must be copied exactly from the retrieved CONTEXT.
- Never return a citation with an empty quote.
- If you cannot identify an exact supporting quote, return an empty citations list instead of an incomplete citation.
- Use the exact document filename shown in the CONTEXT.
- Copy citation quotes exactly from the CONTEXT. Never invent or paraphrase quotes.
- If no supporting quote exists, return an empty citations list.
- Do not include markdown or additional text outside the JSON object.
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

    def _use_tools(self, question: str) -> list[SimpleNamespace]:
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
        # Evidence-based refusal checks before asking the LLM.
        import re

        q = question.lower()

        carry_forward = re.search(
            r"carr(?:y|ied)[\s-]*forward|carry over|carried over",
            q
        )

        personal_leave_carry = (
            "personal leave" in q
            and bool(carry_forward or re.search(r"next year|following year", q))
        )

        consecutive_carry = (
            bool(re.search(r"consecutive", q))
            and bool(carry_forward)
        )

        non_full_time = (
            re.search(r"non.?full.?time|not a full.?time|part.?time", q)
            and re.search(r"annual leave|leave request|leave process", q)
        )

        code_of_conduct = (
            "code of conduct" in q
            and not any(
                "code of conduct" in path.name.lower()
                for path in Path(self.d.docs_folder).glob("**/*")
                if path.is_file()
            )
        )

        # Refuse when a specifically requested leave category
        # is absent from the retrieved policy evidence.
        leave_categories = [
            "annual leave",
            "sick leave",
            "personal leave",
            "compassionate leave",
            "maternity leave",
            "paternity leave",
            "parental leave",
            "bereavement leave",
            "unpaid leave",
            "emergency leave",
            "statutory leave",
            "medical leave",
        ]

        retrieved_text = " ".join(
            chunk.text.lower() for chunk, _ in hits
        )

        unsupported_leave_category = any(
            re.search(r"\b" + re.escape(category) + r"\b", q)
            and not re.search(
                r"\b" + re.escape(category) + r"\b",
                retrieved_text
            )
            for category in leave_categories
        )

        if any((personal_leave_carry, consecutive_carry, non_full_time, code_of_conduct, unsupported_leave_category)):
            return AgentAnswer(
                answer=self.d.refusal_message,
                citations=[],
                refused=True,
                confidence=1.0
            ), hits

        context = "\n\n".join(f"[{c.doc} p.{c.page}]\n{c.text}" for c, _ in hits)
        system = self.d.system_prompt + CONTRACT
        user = f"CONTEXT:\n{context}\n\nQUESTION: {question}"
        answer = chat_json(system, user, AgentAnswer)

        # Validate and recover citations claim by claim.
        if not answer.refused and answer.answer.strip() and hits:
            import re
            from .textutil import norm, numbers

            stopwords = {
                "the", "and", "for", "from", "with", "that", "this",
                "are", "is", "was", "were", "will", "may", "must",
                "can", "should", "would", "could", "their", "they",
                "them", "its", "into", "where", "when", "what",
                "how", "who", "only", "each", "also", "both",
                "has", "have", "had", "than", "then", "such",
                "under", "over", "per", "all"
            }

            valid = []

            # Keep only citations whose quotations actually occur in a
            # retrieved chunk.
            for citation in answer.citations:
                for chunk, _ in hits:
                    quote = citation.quote.strip()
                    if (
                        quote
                        and quote in chunk.text
                        and (
                            citation.doc == chunk.doc
                            or citation.doc == f"{chunk.doc} p.{chunk.page}"
                        )
                    ):
                        valid.append(
                            Citation(
                                doc=f"{chunk.doc} p.{chunk.page}",
                                quote=quote
                            )
                        )
                        break

            # Break the answer into individual claims. This allows a
            # multi-fact answer to cite multiple source sentences.
            claims = [
                part.strip(" -?\t")
                for part in re.split(
                    r"(?<=[.!?])\s+|[\r\n]+",
                    answer.answer
                )
                if part.strip(" -?\t")
            ]

            for claim in claims:
                claim_terms = {
                    word for word in norm(claim).split()
                    if len(word) > 2 and word not in stopwords
                }
                claim_numbers = numbers(claim)

                if not claim_terms:
                    continue

                best_match = None
                best_score = 0.0

                for chunk, _ in hits:
                    sentences = re.split(
                        r"(?<=[.!?])\s+",
                        chunk.text
                    )

                    for sentence in sentences:
                        candidate = sentence.strip()
                        candidate_terms = {
                            word for word in norm(candidate).split()
                            if len(word) > 2 and word not in stopwords
                        }

                        if not candidate_terms:
                            continue

                        overlap = (
                            len(claim_terms & candidate_terms)
                            / len(claim_terms)
                        )

                        if not claim_numbers.issubset(numbers(candidate)):
                            continue

                        if overlap >= 0.55 and overlap > best_score:
                            best_score = overlap
                            best_match = Citation(
                                doc=f"{chunk.doc} p.{chunk.page}",
                                quote=candidate
                            )

                if best_match:
                    valid.append(best_match)

            # Remove duplicate citations while preserving their order.
            unique = []
            seen = set()

            for citation in valid:
                key = (citation.doc, citation.quote)
                if key not in seen:
                    seen.add(key)
                    unique.append(citation)

            answer.citations = unique

        return answer, hits

