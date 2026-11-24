
import csv
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfReader
from docx import Document


def read_document(file_path):
    """Read supported documents and return their text."""

    path = Path(file_path)
    extension = path.suffix.lower()

    if extension == ".pdf":
        reader = PdfReader(str(path))
        pages = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({
                "text": text,
                "page": page_number
            })

        return pages

    elif extension == ".docx":
        document = Document(str(path))
        text = "\n".join(
            paragraph.text for paragraph in document.paragraphs
        )
        return [{"text": text, "page": None}]

    elif extension in [".txt", ".md"]:
        text = path.read_text(encoding="utf-8")
        return [{"text": text, "page": None}]

    elif extension == ".csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.reader(file))

        text = "\n".join(
            " | ".join(row) for row in rows
        )
        return [{"text": text, "page": None}]

    else:
        raise ValueError(f"Unsupported file format: {extension}")


def chunk_text(text, chunk_words=300, overlap=50):
    """Split text into overlapping word chunks."""

    if chunk_words <= 0:
        raise ValueError("chunk_words must be greater than zero")

    if overlap < 0 or overlap >= chunk_words:
        raise ValueError("overlap must be between 0 and chunk_words")

    words = text.split()
    chunks = []
    step = chunk_words - overlap

    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_words])

        if chunk:
            chunks.append(chunk)

    return chunks


def ingest_document(file_path, chunk_words=300, overlap=50):
    """Read a document and return chunks with source information."""

    pages = read_document(file_path)
    results = []

    for page in pages:
        chunks = chunk_text(
            page["text"],
            chunk_words=chunk_words,
            overlap=overlap
        )

        for chunk in chunks:
            results.append({
                "text": chunk,
                "source": Path(file_path).name,
                "page": page["page"]
            })

    return results
def build_chunks(folder, chunk_words=300, overlap=50):
    """Build document chunks from all supported files in a folder."""

    from pathlib import Path

    results = []
    folder = Path(folder)

    supported_extensions = {".pdf", ".docx", ".txt", ".md", ".csv"}

    for file_path in folder.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            results.extend(
                ingest_document(file_path, chunk_words, overlap)
            )

    return results
def make_profile(chunks: list[Chunk]) -> str:
    """Short description of the document folder: filename, size, first 60 words."""
    by_doc: dict[str, list[Chunk]] = {}
    for c in chunks:
        by_doc.setdefault(c.doc, []).append(c)
    lines = []
    for doc, cs in by_doc.items():
        sample = " ".join(cs[0].text.split()[:60])
        lines.append(f"- {doc} ({len(cs)} chunks): {sample} ...")
    return "\n".join(lines)