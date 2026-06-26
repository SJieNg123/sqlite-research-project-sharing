#!/usr/bin/env python3
"""Convert a Markdown file to PDF with the `markdown-pdf` package (markdown-it + PyMuPDF).

Usage:
    pip install markdown-pdf
    python3 md_to_pdf.py                 # REPORT.md -> REPORT.pdf
    python3 md_to_pdf.py in.md out.pdf

Handles:
  * Chinese (CJK) text — this box has no system CJK font, so we embed PyMuPDF's
    built-in CJK font (`china-t`, also covers ASCII) via an @font-face written next
    to the source, then remove it on exit.
  * Relative inline images (e.g. figures/out/*.png) — resolved against the source dir.
  * Figures never get shrunk to fit a page bottom: `fitz.Story` scales an image down to
    the space left on the page, so each figure is placed in its own markdown-pdf Section
    (every Section starts on a fresh page) -> the figure renders at full width.
  * LaTeX math — markdown-it has no math extension, so each `$$ ... $$` block is rendered
    to a PNG via matplotlib mathtext and embedded as an image (inline `$ ... $` -> code);
    falls back to readable text if matplotlib is absent.
"""
import re
import sys
import atexit
from pathlib import Path

import fitz  # PyMuPDF (pulled in by markdown-pdf)
from markdown_pdf import MarkdownPdf, Section

CJK_BUILTIN = "china-t"          # PyMuPDF built-in font with CJK + ASCII glyphs
FONT_FILE = "_md2pdf_cjk.ttf"    # temp font, written into the source dir (Story archive)

CSS_TEMPLATE = """
@font-face {{ font-family: "cjk"; src: url("{font}"); }}
* {{ font-family: "cjk", sans-serif; }}
body {{ font-size: 11px; line-height: 1.5; }}
h1 {{ font-size: 20px; }}
h2 {{ font-size: 15px; border-bottom: 1px solid #bbb; padding-bottom: 3px; }}
h3 {{ font-size: 13px; }}
h4 {{ font-size: 12px; }}
table {{ border-collapse: collapse; font-size: 9.5px; margin: 6px 0; }}
th, td {{ border: 1px solid #999; padding: 2px 5px; }}
th {{ font-weight: bold; border-bottom: 2px solid #555; }}
code {{ background: #f4f4f4; padding: 0 2px; font-size: 10px; }}
pre {{ background: #f4f4f4; padding: 6px; }}
pre code {{ background: none; }}
blockquote {{ border-left: 3px solid #ccc; padding: 1px 9px; color: #333; }}
img {{ max-width: 100%; }}
"""

IMG_LINE = re.compile(r"^!\[.*\]\((figures/[^)]+)\)\s*$")


def _latex_to_text(s: str) -> str:
    """Last-resort readable plain text for a LaTeX fragment (used if matplotlib is absent)."""
    s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
    return (s.replace(r"\qquad", "      ").replace(r"\quad", "   ")
             .replace("\\_", "_").replace("\\", "").strip())


def prepare_math(text: str, root: Path):
    """Render each ``$$ ... $$`` display block to a PNG via matplotlib mathtext and embed
    it (formulas split on ``\\qquad`` -> side by side); inline ``$ ... $`` -> code. Falls
    back to readable text if matplotlib is unavailable. Returns (new_text, [png paths])."""
    created: list = []
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        have_mpl = True
    except Exception:
        have_mpl = False

    idx = [0]

    def render_one(part: str) -> str:
        idx[0] += 1
        fname = f"_md2pdf_math{idx[0]}.png"
        fig = plt.figure()
        fig.text(0.5, 0.5, "$" + part.replace(r"\text", r"\mathrm") + "$",
                 fontsize=16, ha="center", va="center")
        fig.savefig(root / fname, dpi=200, bbox_inches="tight", pad_inches=0.1, transparent=True)
        plt.close(fig)
        created.append(root / fname)
        return f"![formula]({fname})"

    def repl_block(m: "re.Match") -> str:
        parts = [p.strip() for p in re.split(r"\\qquad|\\\\", m.group(1).strip()) if p.strip()]
        out = []
        for part in parts:
            if have_mpl:
                try:
                    out.append(render_one(part))
                    continue
                except Exception:
                    pass
            out.append(f"`{_latex_to_text(part)}`")
        return "\n\n" + "  ".join(out) + "\n\n"

    text = re.sub(r"\$\$(.+?)\$\$", repl_block, text, flags=re.S)
    text = re.sub(r"\$([^$\n]+?)\$", lambda m: f"`{_latex_to_text(m.group(1))}`", text)
    return text, created


def _fig_dims(root: Path) -> dict:
    """{(px_w, px_h): 'figures/out/NAME.png'} for every figure, to map an embedded image
    in the PDF back to its source path (markdown-pdf preserves pixel dimensions)."""
    out = {}
    fdir = root / "figures" / "out"
    if fdir.is_dir():
        for f in fdir.glob("*.png"):
            px = fitz.Pixmap(str(f))
            out[(px.width, px.height)] = f"figures/out/{f.name}"
    return out


def _split_sections(text: str, break_before: set) -> list:
    """Split the markdown into chunks, starting a new chunk (= new PDF page) right before
    each image whose path is in ``break_before``. Images are standalone block lines, so
    this never splits a table/list."""
    chunks, cur = [], []
    for line in text.split("\n"):
        m = IMG_LINE.match(line.strip())
        if m and m.group(1) in break_before and any(c.strip() for c in cur):
            chunks.append("\n".join(cur))
            cur = []
        cur.append(line)
    chunks.append("\n".join(cur))
    return [c for c in chunks if c.strip()]


def main() -> None:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "REPORT.md").resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else src.with_suffix(".pdf")
    if not src.is_file():
        sys.exit(f"source not found: {src}")
    root = src.parent

    # No system CJK font -> embed PyMuPDF's built-in one into the Story archive (root).
    font_path = root / FONT_FILE
    font_path.write_bytes(fitz.Font(CJK_BUILTIN).buffer)
    atexit.register(lambda: font_path.unlink(missing_ok=True))

    css = CSS_TEMPLATE.format(font=FONT_FILE)
    text, math_imgs = prepare_math(src.read_text(encoding="utf-8"), root)
    for mp in math_imgs:
        atexit.register(lambda p=mp: p.unlink(missing_ok=True))

    # Give every figure its own page (fresh Section) so Story can't shrink it to a page
    # bottom; figures render at full width.
    break_before = set(_fig_dims(root).values())
    chunks = _split_sections(text, break_before)
    pdf = MarkdownPdf(toc_level=3, mode="commonmark", optimize=True)
    for chunk in chunks:
        pdf.add_section(Section(chunk, root=str(root)), user_css=css)
    pdf.meta["title"] = src.stem
    pdf.save(str(out))
    print(f"wrote {out}  ({out.stat().st_size // 1024} KB, {len(chunks)} sections)")


if __name__ == "__main__":
    main()
