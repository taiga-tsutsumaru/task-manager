"""Convert スタートガイド.md to a print-friendly Japanese PDF."""
from __future__ import annotations

import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
    PageBreak,
)

# Japanese fonts (built-in CID)
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))   # gothic/sans
pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))      # mincho/serif
JP_FONT = "HeiseiKakuGo-W5"
JP_FONT_MONO = "HeiseiKakuGo-W5"  # reportlab has no mono CJK builtin; fall back to gothic


SRC = Path(__file__).parent / "スタートガイド.md"
OUT = Path(__file__).parent / "スタートガイド.pdf"


def _esc(text: str) -> str:
    """Escape special chars for ReportLab Paragraph XML."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _inline(text: str) -> str:
    """Convert inline markdown (bold, code, link) → ReportLab inline markup."""
    text = _esc(text)
    # bold **...**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # inline code `...`
    text = re.sub(
        r"`([^`]+?)`",
        lambda m: f'<font name="{JP_FONT_MONO}" backColor="#f0f0f0">{m.group(1)}</font>',
        text,
    )
    # links [text](url)
    text = re.sub(
        r"\[([^\]]+?)\]\(([^)]+?)\)",
        r'<link href="\2" color="#1a73e8">\1</link>',
        text,
    )
    return text


# ---- Styles ----
styles = getSampleStyleSheet()

s_h1 = ParagraphStyle(
    "H1", parent=styles["Heading1"], fontName=JP_FONT,
    fontSize=22, leading=28, spaceBefore=4, spaceAfter=12,
    textColor=colors.HexColor("#1a1a1a"),
)
s_h2 = ParagraphStyle(
    "H2", parent=styles["Heading2"], fontName=JP_FONT,
    fontSize=16, leading=22, spaceBefore=16, spaceAfter=8,
    textColor=colors.HexColor("#1a1a1a"),
    borderPadding=(0, 0, 4, 0),
)
s_h3 = ParagraphStyle(
    "H3", parent=styles["Heading3"], fontName=JP_FONT,
    fontSize=13, leading=18, spaceBefore=12, spaceAfter=6,
    textColor=colors.HexColor("#2a2a2a"),
)
s_h4 = ParagraphStyle(
    "H4", parent=styles["Heading4"], fontName=JP_FONT,
    fontSize=11, leading=15, spaceBefore=10, spaceAfter=4,
    textColor=colors.HexColor("#3a3a3a"),
)
s_body = ParagraphStyle(
    "Body", parent=styles["BodyText"], fontName=JP_FONT,
    fontSize=10, leading=15, spaceAfter=6,
    textColor=colors.HexColor("#1a1a1a"),
)
s_li = ParagraphStyle(
    "LI", parent=s_body, leftIndent=14, bulletIndent=2,
    spaceAfter=2,
)
s_code_block = ParagraphStyle(
    "Code", parent=s_body, fontName=JP_FONT_MONO,
    fontSize=9, leading=12, leftIndent=8, rightIndent=8,
    backColor=colors.HexColor("#f5f5f5"),
    borderColor=colors.HexColor("#dddddd"), borderWidth=0.5,
    borderPadding=(6, 8, 6, 8), spaceBefore=4, spaceAfter=8,
    textColor=colors.HexColor("#2a2a2a"),
)
s_callout = ParagraphStyle(
    "Callout", parent=s_body, fontName=JP_FONT,
    leftIndent=10, rightIndent=10, spaceBefore=6, spaceAfter=8,
    backColor=colors.HexColor("#fff8e1"),
    borderColor=colors.HexColor("#f0c040"), borderWidth=0.5,
    borderPadding=(6, 10, 6, 10),
    textColor=colors.HexColor("#1a1a1a"),
)


# ---- Markdown parser → story builder ----

def md_to_story(md_text: str) -> list:
    """Very small markdown subset → reportlab Flowables."""
    story = []
    lines = md_text.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # blank
        if not stripped:
            i += 1
            continue

        # horizontal rule
        if re.match(r"^-{3,}$", stripped):
            story.append(Spacer(1, 4))
            story.append(HRFlowable(
                width="100%", thickness=0.5,
                color=colors.HexColor("#cccccc"),
                spaceBefore=4, spaceAfter=10,
            ))
            i += 1
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            content = _inline(m.group(2))
            style = {1: s_h1, 2: s_h2, 3: s_h3, 4: s_h4}[level]
            story.append(Paragraph(content, style))
            i += 1
            continue

        # fenced code block
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            if i < n:
                i += 1  # skip closing ```
            code_html = "<br/>".join(_esc(l).replace(" ", "&nbsp;") for l in code_lines)
            story.append(Paragraph(code_html, s_code_block))
            continue

        # blockquote / callout
        if stripped.startswith(">"):
            quote_lines = []
            while i < n and lines[i].lstrip().startswith(">"):
                quote_lines.append(re.sub(r"^>\s?", "", lines[i].lstrip()))
                i += 1
            quote_text = "<br/>".join(_inline(l) for l in quote_lines if l.strip())
            story.append(Paragraph(quote_text, s_callout))
            continue

        # table (line starts with | and next line is separator |---|)
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip header + separator
            rows = [header]
            while i < n and lines[i].strip().startswith("|"):
                row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(row)
                i += 1
            # Build Table
            data = [[Paragraph(_inline(c), s_body) for c in row] for row in rows]
            tbl = Table(data, hAlign="LEFT", repeatRows=1)
            tbl.setStyle(TableStyle([
                ("FONT", (0, 0), (-1, -1), JP_FONT, 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a1a1a")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 8))
            continue

        # bullet list (- or *)
        if re.match(r"^[-*]\s+", stripped):
            items = []
            while i < n:
                ls = lines[i].lstrip()
                if not re.match(r"^[-*]\s+", ls):
                    break
                content = re.sub(r"^[-*]\s+", "", ls)
                items.append(Paragraph(f"• {_inline(content)}", s_li))
                i += 1
            for item in items:
                story.append(item)
            story.append(Spacer(1, 4))
            continue

        # ordered list
        if re.match(r"^\d+\.\s+", stripped):
            n_seen = 0
            while i < n:
                ls = lines[i].lstrip()
                m_ol = re.match(r"^(\d+)\.\s+(.*)$", ls)
                if not m_ol:
                    break
                n_seen += 1
                content = m_ol.group(2)
                story.append(Paragraph(f"{n_seen}. {_inline(content)}", s_li))
                i += 1
            story.append(Spacer(1, 4))
            continue

        # paragraph (collect contiguous lines)
        para_lines = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,4}\s|```|>|\||\d+\.\s|[-*]\s|-{3,}$)", lines[i].strip()
        ):
            para_lines.append(lines[i].strip())
            i += 1
        para_text = "".join(para_lines)  # Japanese: no spaces between lines
        story.append(Paragraph(_inline(para_text), s_body))

    return story


def build():
    md_text = SRC.read_text(encoding="utf-8")
    story = md_to_story(md_text)

    doc = SimpleDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="task-manager スタートガイド",
        author="task-manager",
    )

    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(JP_FONT, 8)
        canvas.setFillColor(colors.HexColor("#888888"))
        canvas.drawRightString(
            A4[0] - 20 * mm, 12 * mm,
            f"task-manager v1.0.5 セットアップ手順書  —  p. {doc.page}",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
