"""Apply project-local layout corrections to the generated Substack DOCX."""

from pathlib import Path

from docx import Document
from docx.shared import Pt


PROJECT_DIR = Path(__file__).resolve().parents[1]
DOCX_PATH = PROJECT_DIR / "output" / "article_substack.docx"


def main() -> None:
    document = Document(DOCX_PATH)

    heading_style = document.styles["Heading 2"]
    heading_format = heading_style.paragraph_format
    heading_format.keep_with_next = True
    heading_format.keep_together = True
    heading_format.space_before = Pt(10)
    heading_format.space_after = Pt(6)

    # Direct paragraph settings ensure Word does not inherit the exporter's
    # keep-with-next rule when it lays out a short heading near a page break.
    for paragraph in document.paragraphs:
        if paragraph.style.name == "Heading 2":
            paragraph_format = paragraph.paragraph_format
            paragraph_format.keep_with_next = True
            paragraph_format.keep_together = True
            paragraph_format.space_before = Pt(10)
            paragraph_format.space_after = Pt(6)

    document.save(DOCX_PATH)
    print(DOCX_PATH)


if __name__ == "__main__":
    main()
