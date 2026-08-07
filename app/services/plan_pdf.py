"""
Render a saved plan as a PDF.

Built on ReportLab's platypus flowables rather than drawing to a canvas, so
content paginates automatically - a seven-day workout plan will not run off the
bottom of page one.

The agents emit markdown, so this parses the small subset they actually use
(headings, bullets, numbered lists, bold, emphasis) rather than pulling in a
full markdown library for four constructs.
"""

import html
import io
import re
from datetime import datetime
from typing import List, Optional

# ReportLab is imported lazily.
#
# Importing it at module level meant a missing dependency propagated all the
# way up - plan_pdf -> plans router -> main.py - and stopped the entire API
# from starting. A PDF library should never be able to break login, so the
# import happens inside build_plan_pdf() and its absence degrades to a clear
# error on that one endpoint.
PDF_AVAILABLE = True
try:  # pragma: no cover - availability check only
    import reportlab  # noqa: F401
except ImportError:  # pragma: no cover
    PDF_AVAILABLE = False


# Hex values kept as strings so this module imports without reportlab; they are
# converted to colour objects once it is loaded.
_VIOLET_HEX = "#6D28D9"
_VIOLET_LIGHT_HEX = "#EDE9FE"
_INK_HEX = "#1A1A1A"
_MUTED_HEX = "#667085"
_RULE_HEX = "#E5E7EB"


def _palette():
    from reportlab.lib import colors
    return (
        colors.HexColor(_VIOLET_HEX),
        colors.HexColor(_VIOLET_LIGHT_HEX),
        colors.HexColor(_INK_HEX),
        colors.HexColor(_MUTED_HEX),
        colors.HexColor(_RULE_HEX),
    )


def _styles():
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    VIOLET, _, INK, MUTED, _ = _palette()
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "PlanTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=22, leading=26, textColor=INK, spaceAfter=2, alignment=0,
        ),
        "subtitle": ParagraphStyle(
            "PlanSubtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=9.5, leading=13, textColor=MUTED, spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "PlanH1", parent=base["Heading1"], fontName="Helvetica-Bold",
            fontSize=14, leading=18, textColor=VIOLET, spaceBefore=14, spaceAfter=5,
        ),
        "h2": ParagraphStyle(
            "PlanH2", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=12, leading=16, textColor=INK, spaceBefore=11, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "PlanH3", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=14, textColor=VIOLET, spaceBefore=9, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "PlanBody", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, leading=15, textColor=INK, spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "PlanBullet", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, leading=14.5, textColor=INK,
        ),
        "footer": ParagraphStyle(
            "PlanFooter", parent=base["Normal"], fontName="Helvetica",
            fontSize=7.5, leading=10, textColor=MUTED, alignment=TA_CENTER,
        ),
    }


def _inline(text: str) -> str:
    """Markdown inline formatting -> ReportLab's mini-HTML."""
    safe = html.escape(text)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<i>\1</i>", safe)
    safe = re.sub(r"`([^`]+?)`", r"<font face='Courier'>\1</font>", safe)
    return safe


def _markdown_to_flowables(md: str, s) -> List:
    """Convert the markdown subset the agents emit into flowables."""
    from reportlab.platypus import ListFlowable, ListItem, Paragraph
    VIOLET = _palette()[0]
    flow = []
    pending_bullets: List[str] = []

    def flush_bullets():
        nonlocal pending_bullets
        if not pending_bullets:
            return
        flow.append(ListFlowable(
            [ListItem(Paragraph(b, s["bullet"]), leftIndent=10) for b in pending_bullets],
            bulletType="bullet", bulletColor=VIOLET, bulletFontSize=6,
            leftIndent=12, spaceBefore=2, spaceAfter=6,
        ))
        pending_bullets = []

    for raw in (md or "").split("\n"):
        line = raw.rstrip()

        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_bullets()
            level = min(len(heading.group(1)), 3)
            flow.append(Paragraph(_inline(heading.group(2)), s[f"h{level}"]))
            continue

        bullet = re.match(r"^\s*[-*•]\s+(.*)$", line)
        if bullet:
            pending_bullets.append(_inline(bullet.group(1)))
            continue

        numbered = re.match(r"^\s*(\d+)\.\s+(.*)$", line)
        if numbered:
            pending_bullets.append(f"<b>{numbered.group(1)}.</b> {_inline(numbered.group(2))}")
            continue

        if not line.strip():
            flush_bullets()
            continue

        flush_bullets()
        flow.append(Paragraph(_inline(line), s["body"]))

    flush_bullets()
    return flow


def _meta_table(pairs, s):
    """Small key/value strip under the title."""
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle
    _, VIOLET_LIGHT, _, _, RULE = _palette()
    pairs = [(k, v) for k, v in pairs if v]
    if not pairs:
        return None
    data = [[Paragraph(f"<font color='#667085' size='7.5'>{html.escape(str(k)).upper()}</font><br/>"
                       f"<font size='9.5'><b>{html.escape(str(v))}</b></font>", s["body"])
             for k, v in pairs]]
    t = Table(data, colWidths=[(170 * mm) / len(pairs)] * len(pairs))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), VIOLET_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _footer(canvas, doc, owner: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    _, _, _, MUTED, RULE = _palette()
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(20 * mm, 12 * mm, f"NutriPlan · {owner}")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
    canvas.restoreState()


def build_plan_pdf(
    *,
    title: str,
    content: str,
    plan_type: str,
    owner_name: str = "",
    created_at: Optional[datetime] = None,
    meta_pairs: Optional[List] = None,
    disclaimer: Optional[str] = None,
) -> bytes:
    """Render one saved plan and return the PDF bytes."""
    if not PDF_AVAILABLE:
        raise RuntimeError(
            "PDF export needs the 'reportlab' package. Install it with: pip install reportlab"
        )

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer
    VIOLET, _, _, _, RULE = _palette()

    s = _styles()
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title=title, author="NutriPlan",
    )

    story = [Paragraph(html.escape(title), s["title"])]

    when = (created_at or datetime.utcnow()).strftime("%d %B %Y")
    who = f" · prepared for {html.escape(owner_name)}" if owner_name else ""
    story.append(Paragraph(f"{when}{who}", s["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=1.2, color=VIOLET, spaceAfter=10))

    table = _meta_table(meta_pairs or [], s)
    if table is not None:
        story.append(table)
        story.append(Spacer(1, 10))

    story.extend(_markdown_to_flowables(content, s))

    if disclaimer:
        story.append(Spacer(1, 14))
        story.append(HRFlowable(width="100%", thickness=0.5, color=RULE, spaceAfter=8))
        story.append(Paragraph(html.escape(disclaimer), s["footer"]))

    doc.build(
        story,
        onFirstPage=lambda c, d: _footer(c, d, owner_name),
        onLaterPages=lambda c, d: _footer(c, d, owner_name),
    )
    return buf.getvalue()


# Per-type presentation. Keeps the router free of copy.
PLAN_META = {
    "workout": {
        "title": "Your Workout Plan",
        "filename": "workout-plan",
        "disclaimer": "This is a general exercise plan, not medical or rehabilitation advice. "
                      "Stop if something hurts, and speak to a physiotherapist or doctor about any injury.",
    },
    "budget_meal_plan": {
        "title": "Your Budget Meal Plan",
        "filename": "budget-meal-plan",
        "disclaimer": "Costs are estimates and vary by location and season.",
    },
    "regional": {
        "title": "Your Regional Meal Plan",
        "filename": "regional-meal-plan",
        "disclaimer": "Adapt seasoning and substitutions to what is available near you.",
    },
    "weekly_meal_plan": {
        "title": "Your 7-Day Meal Plan",
        "filename": "weekly-meal-plan",
        "disclaimer": "Nutrition figures are estimates. Adjust portions to how you actually feel and progress.",
    },
    "recipe": {
        "title": "Your Recipe",
        "filename": "recipe",
        "disclaimer": "Check for allergens before cooking.",
    },
}
