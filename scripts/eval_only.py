
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forgeai.judge import summarize
from forgeai.optimizer import run_evals
from forgeai.schemas import AgentDef, EvalCase

import argparse

ap = argparse.ArgumentParser()
ap.add_argument("project")
ap.add_argument("--agent", default="agent/agent.yaml")
ap.add_argument("--tag", default="run")
a = ap.parse_args()

project = Path(a.project)

agent_path = project / a.agent
eval_path = project / "evals" / "evals.json"

definition = AgentDef(
    **yaml.safe_load(agent_path.read_text(encoding="utf-8"))
)

cases = [
    EvalCase(**item)
    for item in json.loads(eval_path.read_text(encoding="utf-8"))
]

print(f"Running {len(cases)} evaluation cases...")

results = run_evals(definition, cases)

summary = summarize(results)

print("\nFINAL SUMMARY")
print(json.dumps(summary, indent=2))

out = project / "scorecard"
out.mkdir(parents=True, exist_ok=True)

result_path = out / f"eval_only_{a.tag}.json"

result_path.write_text(
    json.dumps([r.model_dump() for r in results], indent=2),
    encoding="utf-8"
)

print(f"\nResults saved to: {result_path}")
