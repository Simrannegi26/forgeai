
import sys
from pathlib import Path

from forgeai.evalgen import generate as gen_evals
from forgeai.generator import generate
from forgeai.ingest import build_chunks
from forgeai.retrieval import Index
from forgeai.schemas import Requirements

brief, docs, out = sys.argv[1:4]

index = Index(build_chunks(docs))

req = Requirements.model_validate_json(
    Path(out, "requirements", "requirements.json").read_text(
        encoding="utf-8"
    )
)

defn, log = generate(req, brief, index, docs, out)

print("TOOLS:", [t.name for t in defn.tools])

cases = gen_evals(req, index, out)

for c in cases[:6]:
    print(c.id, c.type, "|", c.question, "|", c.key_facts)
