
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

styles = getSampleStyleSheet()


def txt_to_pdf(src: Path, dst: Path):
    story = []
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            story.append(Spacer(1, 8))
            continue
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        heading = line.startswith("#") or line.isupper()
        story.append(Paragraph(safe.lstrip("# "), styles["Heading2" if heading else "BodyText"]))
    SimpleDocTemplate(str(dst), pagesize=A4).build(story)


if __name__ == "__main__":
    raw, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for f in sorted(raw.glob("*.txt")):
        txt_to_pdf(f, out / (f.stem + ".pdf"))
        print("made", f.stem + ".pdf")
