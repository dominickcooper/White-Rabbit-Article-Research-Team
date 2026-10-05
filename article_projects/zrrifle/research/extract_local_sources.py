"""Mechanically extract the supplied EPUB and saved HTML into reviewable text.

The originals in ``sources/`` remain untouched.  Output is deliberately kept
under this article project's generated research directory.
"""

from __future__ import annotations

import html
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "sources"
OUTPUT = ROOT / "research" / "generated" / "local_text"


def clean_markup(raw: bytes) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = soup.get_text("\n")
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_epub(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        container = ElementTree.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next(
            node.attrib["full-path"]
            for node in container.iter()
            if node.tag.endswith("rootfile")
        )
        package_dir = Path(rootfile).parent
        package = ElementTree.fromstring(archive.read(rootfile))
        manifest = {
            node.attrib["id"]: node.attrib["href"]
            for node in package.iter()
            if node.tag.endswith("item") and "id" in node.attrib and "href" in node.attrib
        }
        spine = [
            node.attrib["idref"]
            for node in package.iter()
            if node.tag.endswith("itemref") and "idref" in node.attrib
        ]
        sections: list[str] = []
        entries: list[dict[str, object]] = []
        for position, item_id in enumerate(spine, start=1):
            href = manifest.get(item_id)
            if not href:
                continue
            member = (package_dir / href).as_posix()
            if member not in archive.namelist():
                continue
            text = clean_markup(archive.read(member))
            if not text:
                continue
            sections.append(f"===== SPINE {position:03d}: {member} =====\n\n{text}")
            entries.append({"position": position, "member": member, "characters": len(text)})
    output_path = OUTPUT / "Bond_of_Secrecy.txt"
    output_path.write_text("\n\n".join(sections), encoding="utf-8")
    return {"source": path.name, "output": str(output_path), "sections": entries}


def extract_html(path: Path) -> dict[str, object]:
    text = clean_markup(path.read_bytes())
    output_path = OUTPUT / "ZR_Rifle_saved_webpage.txt"
    output_path.write_text(text, encoding="utf-8")
    return {"source": path.name, "output": str(output_path), "characters": len(text)}


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    epub = next(SOURCES.glob("*.epub"))
    saved_page = next(SOURCES.glob("*.htm*"))
    index = {"epub": extract_epub(epub), "html": extract_html(saved_page)}
    (OUTPUT / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(json.dumps(index, indent=2))


if __name__ == "__main__":
    main()
