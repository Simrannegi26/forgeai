from pydantic import BaseModel, Field


class Retrieval(BaseModel):
    chunk_words: int = 300
    overlap: int = 50
    top_k: int = 4
    hybrid: bool = True


class ToolSpec(BaseModel):
    name: str
    justification: str = ""


class AgentDef(BaseModel):
    name: str
    docs_folder: str
    system_prompt: str
    retrieval: Retrieval = Field(default_factory=Retrieval)
    tools: list[ToolSpec] = Field(default_factory=list)
    output_contract: str = "JSON {answer, citations[{doc, quote}], refused, confidence}"
    refusal_message: str = "I can't answer that from the available documents."
    must_refuse: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    doc: str
    quote: str


class AgentAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    confidence: float = 0.5


# ---------- generic LLM output shapes ----------
class Questions(BaseModel):
    questions: list[str]


class Topics(BaseModel):
    topics: list[str]


class OneQuestion(BaseModel):
    question: str


class AnswerOut(BaseModel):
    answer: str


class YesNo(BaseModel):
    answer: str  # "yes" or "no"


# ---------- requirements ----------
class QA(BaseModel):
    question: str
    answer: str
    assumed: bool = False


class TopicCheck(BaseModel):
    topic: str
    status: str  # supported | partial | unsupported
    similarity: float
    llm_yes: bool
    lexical: float


class ReqDraft(BaseModel):
    agent_name: str = "agent"
    scope: str
    audience: str
    tone: str
    must_answer: list[str] = Field(default_factory=list)
    must_refuse: list[str] = Field(default_factory=list)


class Requirements(ReqDraft):
    gaps: list[str] = Field(default_factory=list)
    qa: list[QA] = Field(default_factory=list)
    topic_checks: list[TopicCheck] = Field(default_factory=list)


# ---------- generator ----------
class ToolProposal(BaseModel):
    tools: list[ToolSpec] = Field(default_factory=list)


class ToolCall(BaseModel):
    tool: str | None = None
    args: dict = Field(default_factory=dict)


class PromptOut(BaseModel):
    system_prompt: str


class RuleOut(BaseModel):
    rule: str


# ---------- evals + judging ----------
class GenQA(BaseModel):
    question: str
    answer: str
    key_facts: list[str]


class EvalCase(BaseModel):
    id: str = ""
    type: str  # answerable | out_of_scope | edge
    subtype: str = ""
    question: str
    expected_refuse: bool
    expected_docs: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    reference_answer: str = ""


class CaseResult(BaseModel):
    id: str
    type: str
    question: str
    expected_refuse: bool
    answer: str
    refused: bool
    citations: list[Citation] = Field(default_factory=list)
    retrieved_docs: list[str] = Field(default_factory=list)
    refusal_ok: bool
    correct: bool | None = None
    grounded: bool | None = None
    method: str = "deterministic"
    passed: bool = False
    category: str | None = None
