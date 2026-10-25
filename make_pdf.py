#!/usr/bin/env python3
"""Convert VLM_Reliability_Toolkit_Explained.md to a styled PDF using reportlab."""
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, ListFlowable, ListItem
)

import sys

MD_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("VLM_Reliability_Toolkit_Explained.md")
OUT_PATH = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("VLM_Reliability_Toolkit_Explained.pdf")

# ---------- Styles ----------
title_style = ParagraphStyle(
    "Title", fontName="Helvetica-Bold", fontSize=20, leading=26,
    textColor=colors.HexColor("#1a1a2e"), alignment=TA_CENTER, spaceAfter=14,
)
subtitle_style = ParagraphStyle(
    "Subtitle", fontName="Helvetica-Oblique", fontSize=11, leading=15,
    textColor=colors.HexColor("#4a4a6a"), alignment=TA_CENTER, spaceAfter=18,
)
h1_style = ParagraphStyle(
    "H1", fontName="Helvetica-Bold", fontSize=15, leading=20,
    textColor=colors.HexColor("#2d2d44"), spaceBefore=16, spaceAfter=7,
)
h2_style = ParagraphStyle(
    "H2", fontName="Helvetica-Bold", fontSize=12, leading=16,
    textColor=colors.HexColor("#3d3d5a"), spaceBefore=12, spaceAfter=5,
)
body_style = ParagraphStyle(
    "Body", fontName="Helvetica", fontSize=10, leading=14,
    textColor=colors.HexColor("#222222"), spaceAfter=6, alignment=TA_LEFT,
)
bullet_style = ParagraphStyle(
    "Bullet", parent=body_style, leftIndent=16, bulletIndent=6, spaceAfter=3,
)
table_cell_style = ParagraphStyle(
    "TableCell", fontName="Helvetica", fontSize=8.5, leading=11,
    textColor=colors.HexColor("#222222"),
)
table_header_style = ParagraphStyle(
    "TableHeader", fontName="Helvetica-Bold", fontSize=8.5, leading=11,
    textColor=colors.white,
)
note_style = ParagraphStyle(
    "Note", fontName="Helvetica-Oblique", fontSize=9, leading=12,
    textColor=colors.HexColor("#555555"), spaceAfter=6,
)

# ---------- Markdown parsing helpers ----------
def inline_to_paragraph(text: str) -> str:
    """Convert basic markdown inline syntax to reportlab-compatible HTML."""
    # **bold**
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # *italic* (but not list markers)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    # `code`
    text = re.sub(r"`(.+?)`", r"<font face='Courier'><b>\1</b></font>", text)
    # escape any remaining < > that aren't tags
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    # re-allow our tags
    text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    text = text.replace("&lt;font face='Courier'><b&gt;", "<font face='Courier'><b>")
    text = text.replace("&lt;/b&gt;&lt;/font&gt;", "</b></font>")
    return text


def build_table(lines):
    """Build a reportlab Table from markdown table lines."""
    rows = []
    for line in lines:
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append([Paragraph(inline_to_paragraph(c), table_cell_style) for c in cells])
    if not rows:
        return None
    ncols = len(rows[0])
    col_widths = [6.5 * inch / ncols] * ncols
    t = Table(rows, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a4a6a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbbbbb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f8")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    t.setStyle(TableStyle(style))
    return t


def main():
    raw = MD_PATH.read_text(encoding="utf-8")
    lines = raw.split("\n")

    story = []

    # Title from first H1
    if lines and lines[0].startswith("# "):
        story.append(Paragraph(lines[0][2:].strip(), title_style))
        story.append(Spacer(1, 6))
        # subtitle
        idx = 1
        while idx < len(lines) and (lines[idx].strip() == "" or lines[idx].startswith("---")):
            idx += 1
        # find a short descriptive line
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#4a4a6a"), spaceAfter=10))

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Horizontal rule
        if stripped == "---":
            story.append(HRFlowable(width="100%", thickness=0.7, color=colors.HexColor("#cccccc"), spaceBefore=4, spaceAfter=8))
            i += 1
            continue

        # H1
        if stripped.startswith("# "):
            story.append(Paragraph(stripped[2:].strip(), h1_style))
            i += 1
            continue
        # H2
        if stripped.startswith("## "):
            story.append(Paragraph(stripped[3:].strip(), h2_style))
            i += 1
            continue
        # H3
        if stripped.startswith("### "):
            story.append(Paragraph(stripped[4:].strip(), h2_style))
            i += 1
            continue

        # Blank line
        if stripped == "":
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Table block
        if stripped.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            t = build_table(table_lines)
            if t:
                story.append(t)
                story.append(Spacer(1, 8))
            continue

        # List block (bulleted)
        if stripped.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(ListItem(Paragraph(inline_to_paragraph(lines[i].strip()[2:]), bullet_style)))
                i += 1
            story.append(ListFlowable(items, bulletType="bullet", start="circle", leftIndent=14, spaceAfter=6))
            continue

        # Numbered list
        if re.match(r"^\d+\. ", stripped):
            items = []
            while i < len(lines) and re.match(r"^\d+\. ", lines[i].strip()):
                items.append(ListItem(Paragraph(inline_to_paragraph(re.sub(r"^\d+\.\s*", "", lines[i].strip())), bullet_style)))
                i += 1
            story.append(ListFlowable(items, bulletType="1", leftIndent=16, spaceAfter=6))
            continue

        # Regular paragraph
        story.append(Paragraph(inline_to_paragraph(stripped), body_style))
        i += 1

    doc = SimpleDocTemplate(
        str(OUT_PATH), pagesize=letter,
        leftMargin=0.8 * inch, rightMargin=0.8 * inch,
        topMargin=0.7 * inch, bottomMargin=0.7 * inch,
        title="VLM Reliability Toolkit — Explained",
        author="VLM Reliability Toolkit",
    )
    doc.build(story)
    print(f"PDF written to {OUT_PATH.resolve()}")


if __name__ == "__main__":
    main()
