from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def render(name: str, **kw) -> str:
    text = (PROMPT_DIR / f"{name}.txt").read_text(encoding="utf-8")
    for k, v in kw.items():
        text = text.replace("{{" + k + "}}", str(v))
    return text