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
  * Relative inline images (e.g. figures/out/*.png) — resolved against the source dir
    (the markdown-pdf "archive"), so the figures embed.

Limitations:
  * `$$ ... $$` LaTeX math is not rendered (markdown-it has no math extension);
    it appears literally. The report has only the two e2e formulas in §3.4.
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
th {{ background: #eee; }}
code {{ background: #f4f4f4; padding: 0 2px; font-size: 10px; }}
pre {{ background: #f4f4f4; padding: 6px; }}
pre code {{ background: none; }}
blockquote {{ border-left: 3px solid #ccc; padding: 1px 9px; color: #333; }}
img {{ max-width: 100%; }}
"""


def soften_display_math(text: str) -> str:
    """markdown-it has no math extension, so a ``$$ ... $$`` block would print as raw
    LaTeX. Render it as plain readable text instead (only touches ``$$``-delimited
    blocks; inline ``$`` is left alone to avoid hitting shell/`$` in code)."""
    def clean(m: "re.Match") -> str:
        s = m.group(1)
        s = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
        s = (s.replace(r"\qquad", "      ").replace(r"\quad", "   ")
               .replace("\\_", "_").replace("\\", "").strip())
        return f"\n`{s}`\n"
    return re.sub(r"\$\$(.+?)\$\$", clean, text, flags=re.S)


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
    text = soften_display_math(src.read_text(encoding="utf-8"))
    pdf = MarkdownPdf(toc_level=3, mode="commonmark", optimize=True)
    pdf.add_section(Section(text, root=str(root)), user_css=css)
    pdf.meta["title"] = src.stem
    pdf.save(str(out))
    print(f"wrote {out}  ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
