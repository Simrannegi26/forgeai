
from pydantic import BaseModel, Field


class Retrieval(BaseModel):
    chunk_words: int = 300
    overlap: int = 50
    top_k: int = 4
    hybrid: bool = True


class ToolSpec(BaseModel):
    name: str
    justification: str


class AgentDef(BaseModel):
    name: str
    docs_folder: str
    system_prompt: str
    retrieval: Retrieval = Field(default_factory=Retrieval)
    tools: list[ToolSpec] = Field(default_factory=list)
    refusal_message: str = "I can't answer that from the available documents."


class Citation(BaseModel):
    doc: str
    quote: str


class AgentAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    refused: bool = False
    confidence: float = 0.5
