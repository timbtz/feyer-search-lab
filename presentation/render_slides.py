"""Render the final pitch and original challenge brief (requires PyMuPDF)."""
import hashlib
import json
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent
PAGES = {2: "02-profile", 3: "03-sparse", 4: "04-host-engine",
         5: "05-last-second", 6: "06-validation", 8: "08-agent-loop",
         9: "09-search", 13: "13-faster-answers"}


def main():
    source = ROOT / "faster-answers.pdf"
    output = ROOT / "slides"
    output.mkdir(exist_ok=True)
    slides = []
    with fitz.open(source) as document:
        for number, name in PAGES.items():
            page = document[number - 1]
            scale = 1440 / page.rect.width
            target = output / (name + ".png")
            page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(target)
            slides.append({"page": number, "file": "slides/" + target.name,
                           "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    manifest = {"source": "../faster-answers.pdf",
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "width_px": 1440, "slides": slides}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    source = ROOT.parent / "challenge.pdf"
    output = ROOT / "challenge"
    output.mkdir(exist_ok=True)
    target = output / "01-brief.png"
    with fitz.open(source) as document:
        page = document[0]
        scale = 1200 / page.rect.width
        page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).save(target)
    manifest = {"source": "../../challenge.pdf", "page": 1,
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "file": target.name, "width_px": 1200,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
