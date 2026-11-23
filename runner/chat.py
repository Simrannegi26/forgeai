
import sys

import yaml

from forgeai.agent import Agent
from forgeai.schemas import AgentDef


def main(path: str):
    with open(path, encoding="utf-8") as f:
        definition = AgentDef(**yaml.safe_load(f))
    print(f"Loading agent '{definition.name}' ...")
    agent = Agent(definition)
    print("Ready. Type 'exit' to quit.\n")
    while True:
        question = input("you> ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue
        answer, _ = agent.ask(question)
        print(f"\nagent> {answer.answer}")
        if answer.refused:
            print("  [refused]")
        for c in answer.citations:
            print(f'  source: {c.doc}: "{c.quote}"')
        print()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m runner.chat agents/your_agent.yaml")
        sys.exit(1)
    main(sys.argv[1])