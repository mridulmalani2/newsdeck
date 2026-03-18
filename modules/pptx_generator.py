"""
PPTX Generator — Creates 1-slider slides from article data.

Uses the slide_template.pptx (converted from .potx) as the base.
All element positions are fixed from the template. Text is handled
intelligently: font size fallback, conditional bullets, word-limit
awareness, and normAutofit for PowerPoint-level shrinking.

Shape reference (from template):
  Titre 42        (id=43)  — Article headline
  Rectangle 5     (id=6)   — Category tag (red box, top-left)
  ZoneTexte 6     (id=7)   — Date (below category)
  Rectangle 7     (id=8)   — "SUMMARY & RELEVANT INFORMATION" label
  Rectangle 8     (id=9)   — "IMPLICATIONS" label
  Rectangle 9     (id=10)  — "CREDIBILITY" label
  Rectangle 1     (id=2)   — "RELEVANCE" label
  Rectangle 13    (id=14)  — Summary + relevant info content
  Rectangle 16    (id=17)  — Implications content
  ZoneTexte 4     (id=15)  — Source URL
  Picture 15      (id=16)  — Article image (single, left side)
  Star: 5 Points 10/11/12  — Credibility stars
  Star: 5 Points 22/24/25  — Relevance stars
  TGR Logo                  — Inherited from slide layout (no action needed)
"""

import logging
import os
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.oxml.ns import qn
from lxml import etree

from config import TemplateLayout as TL, Grid, TEMPLATE_PATH, SLIDES_DIR

logger = logging.getLogger(__name__)


# ── Data Model ──────────────────────────────────────────────────────────

@dataclass
class ArticleData:
    title: str = ""
    summary: str = ""
    relevant_info: str = ""
    implications: str = ""
    implications_sub: list = field(default_factory=list)
    category: str = "GENERAL INNOVATION"
    publication_date: str = ""
    source_url: str = ""
    source_name: str = ""
    credibility_score: float = 3.0
    relevancy_score: float = 3.0
    article_image: Optional[str] = None


# ── Error text filtering ────────────────────────────────────────────────

_ERROR_INDICATORS = [
    "parsing failed", "evaluation parsing failed", "using default scores",
    "failed to", "error:", "exception:", "traceback",
    "no data available", "could not parse", "api error",
]


def _is_error_text(text: str) -> bool:
    if not text:
        return False
    low = text.lower().strip()
    return any(ind in low for ind in _ERROR_INDICATORS)


def _sanitize(article: ArticleData) -> ArticleData:
    if _is_error_text(article.relevant_info):
        logger.warning(f"Filtered error from relevant_info: {article.relevant_info[:60]}")
        article.relevant_info = ""
    if article.summary:
        lines = article.summary.split("\n")
        article.summary = "\n".join(l for l in lines if not _is_error_text(l))
    if _is_error_text(article.implications):
        logger.warning(f"Filtered error from implications: {article.implications[:60]}")
        article.implications = ""
    if article.implications_sub:
        article.implications_sub = [s for s in article.implications_sub if not _is_error_text(s)]
    return article


# ── Helpers ─────────────────────────────────────────────────────────────

def _format_date(date_str: str) -> str:
    if not date_str:
        return datetime.now().strftime("%d/%m/%Y")
    if len(date_str) == 10 and date_str[2] == "/" and date_str[5] == "/":
        return date_str
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%d-%m-%Y", "%m/%d/%Y"]:
        try:
            dt = datetime.strptime(date_str.split("+")[0].split("Z")[0], fmt)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return date_str


def _word_count(text: str) -> int:
    return len(text.split())


def _find_shape_by_name(slide, name: str):
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    return None


def _find_shape_by_id(slide, shape_id: int):
    for shape in slide.shapes:
        if shape.shape_id == shape_id:
            return shape
    return None


def score_to_stars(score: float, max_stars: int = 3) -> int:
    """0-5 score → 1-3 stars."""
    if score <= 1.7:
        return 1
    elif score <= 3.3:
        return 2
    else:
        return 3


# ── Font size fallback ──────────────────────────────────────────────────

# Approximate character capacity for the content boxes at each font size.
# Box inner area: ~5.82" wide × 2.37" high.
_FONT_CAPACITY = {
    1400: 120,   # 14pt — ~120 words
    1200: 160,   # 12pt — ~160 words
    1100: 185,   # 11pt — ~185 words
    1000: 220,   # 10pt — ~220 words
}


def _choose_font_size(text: str, default_size: int = 1400, min_size: int = 1000) -> int:
    """Pick the largest font size that fits the text within the box.

    Uses word count as a proxy. Returns font size in hundredths of a point.
    """
    wc = _word_count(text)
    for size in sorted(_FONT_CAPACITY.keys(), reverse=True):
        if size < min_size:
            continue
        if size > default_size:
            continue
        if wc <= _FONT_CAPACITY[size]:
            return size
    return min_size


# ── Grid layout helpers ────────────────────────────────────────────────


def _reposition_shape(shape, left, top, width=None, height=None):
    """Reposition a shape to grid-derived coordinates."""
    el = shape._element
    # Handle both p:sp and p:pic elements
    spPr = el.find(qn("p:spPr"))
    if spPr is None:
        return
    xfrm = spPr.find(qn("a:xfrm"))
    if xfrm is None:
        return
    off = xfrm.find(qn("a:off"))
    if off is not None:
        off.set("x", str(int(left)))
        off.set("y", str(int(top)))
    ext = xfrm.find(qn("a:ext"))
    if ext is not None:
        if width is not None:
            ext.set("cx", str(int(width)))
        if height is not None:
            ext.set("cy", str(int(height)))


def _set_text_padding(shape, left=None, right=None, top=None, bottom=None):
    """Set internal text margins on a shape's text body."""
    txBody = shape._element.find(qn("p:txBody"))
    if txBody is None:
        return
    bodyPr = txBody.find(qn("a:bodyPr"))
    if bodyPr is None:
        return
    if left is not None:
        bodyPr.set("lIns", str(int(left)))
    if right is not None:
        bodyPr.set("rIns", str(int(right)))
    if top is not None:
        bodyPr.set("tIns", str(int(top)))
    if bottom is not None:
        bodyPr.set("bIns", str(int(bottom)))


def _style_section_header(shape):
    """Style a section header: bold, reduced color (80% black), ALL CAPS."""
    if not shape or not shape.has_text_frame:
        return
    txBody = shape._element.find(qn("p:txBody"))
    if txBody is None:
        return
    for p in txBody.findall(qn("a:p")):
        for r in p.findall(qn("a:r")):
            rPr = r.find(qn("a:rPr"))
            if rPr is None:
                rPr = etree.Element(qn("a:rPr"))
                r.insert(0, rPr)
            rPr.set("b", "1")
            # Remove existing color fills, apply 80% black
            for fill in rPr.findall(qn("a:solidFill")):
                rPr.remove(fill)
            solidFill = etree.SubElement(rPr, qn("a:solidFill"))
            srgbClr = etree.SubElement(solidFill, qn("a:srgbClr"))
            srgbClr.set("val", Grid.HEADER_COLOR)
            # Uppercase text
            t = r.find(qn("a:t"))
            if t is not None and t.text:
                t.text = t.text.upper()


def _add_section_divider(slide, left, top, width):
    """Add a subtle horizontal divider line above a section."""
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.dml.color import RGBColor

    divider = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        int(left), int(top),
        int(width), Grid.DIVIDER_H,
    )
    divider.fill.solid()
    divider.fill.fore_color.rgb = RGBColor(200, 200, 200)
    divider.line.fill.background()


def _apply_grid_layout(slide):
    """Reposition all elements to grid-derived positions and apply visual hierarchy."""

    divider_width = Grid.RIGHT_EDGE - Grid.LABEL_COL_X

    # ── Header zone ──

    shape = _find_shape_by_name(slide, "Rectangle 5")  # Category
    if shape:
        _reposition_shape(shape, TL.CATEGORY_X, TL.CATEGORY_Y,
                          TL.CATEGORY_W, TL.CATEGORY_H)

    shape = _find_shape_by_name(slide, "ZoneTexte 6")  # Date
    if shape:
        _reposition_shape(shape, TL.DATE_X, TL.DATE_Y,
                          TL.DATE_W, TL.DATE_H)

    shape = _find_shape_by_name(slide, "Titre 42")  # Title
    if shape:
        _reposition_shape(shape, TL.TITLE_X, TL.TITLE_Y,
                          TL.TITLE_W, TL.TITLE_H)

    # ── Summary section ──

    _add_section_divider(slide, Grid.LABEL_COL_X,
                         Grid.CONTENT_Y - Grid.DIVIDER_OFFSET,
                         divider_width)

    shape = _find_shape_by_name(slide, "Rectangle 7")  # Summary label
    if shape:
        _reposition_shape(shape, TL.SUMMARY_LABEL_X, TL.SUMMARY_LABEL_Y,
                          TL.SUMMARY_LABEL_W, TL.SUMMARY_LABEL_H)
        _style_section_header(shape)

    shape = _find_shape_by_name(slide, "Rectangle 13")  # Summary text
    if shape:
        _reposition_shape(shape, TL.SUMMARY_TEXT_X, TL.SUMMARY_TEXT_Y,
                          TL.SUMMARY_TEXT_W, TL.SUMMARY_TEXT_H)
        _set_text_padding(shape, Grid.PADDING_X, Grid.PADDING_X,
                          Grid.PADDING_Y, Grid.PADDING_Y)

    # ── Implications section ──

    _add_section_divider(slide, Grid.LABEL_COL_X,
                         Grid.IMPL_Y - Grid.DIVIDER_OFFSET,
                         divider_width)

    shape = _find_shape_by_name(slide, "Rectangle 8")  # Implications label
    if shape:
        _reposition_shape(shape, TL.IMPLICATIONS_LABEL_X, TL.IMPLICATIONS_LABEL_Y,
                          TL.IMPLICATIONS_LABEL_W, TL.IMPLICATIONS_LABEL_H)
        _style_section_header(shape)

    shape = _find_shape_by_name(slide, "Rectangle 16")  # Implications text
    if shape:
        _reposition_shape(shape, TL.IMPLICATIONS_TEXT_X, TL.IMPLICATIONS_TEXT_Y,
                          TL.IMPLICATIONS_TEXT_W, TL.IMPLICATIONS_TEXT_H)
        _set_text_padding(shape, Grid.PADDING_X, Grid.PADDING_X,
                          Grid.PADDING_Y, Grid.PADDING_Y)

    # ── Footer section ──

    _add_section_divider(slide, Grid.LABEL_COL_X,
                         Grid.FOOTER_Y - Grid.DIVIDER_OFFSET,
                         divider_width)

    shape = _find_shape_by_name(slide, "Rectangle 9")  # Credibility label
    if shape:
        _reposition_shape(shape, TL.CREDIBILITY_LABEL_X, TL.CREDIBILITY_LABEL_Y,
                          TL.CREDIBILITY_LABEL_W, TL.CREDIBILITY_LABEL_H)
        _style_section_header(shape)

    shape = _find_shape_by_name(slide, "Rectangle 1")  # Relevance label
    if shape:
        _reposition_shape(shape, TL.RELEVANCE_LABEL_X, TL.RELEVANCE_LABEL_Y,
                          TL.RELEVANCE_LABEL_W, TL.RELEVANCE_LABEL_H)
        _style_section_header(shape)

    # Credibility stars
    cred_star_xs = [TL.CRED_STAR1_X, TL.CRED_STAR2_X, TL.CRED_STAR3_X]
    for i, name in enumerate(["Star: 5 Points 10", "Star: 5 Points 11", "Star: 5 Points 12"]):
        shape = _find_shape_by_name(slide, name)
        if shape:
            _reposition_shape(shape, cred_star_xs[i], TL.CRED_STARS_Y,
                              TL.STAR_SIZE, TL.STAR_SIZE)

    # Relevance stars
    rel_star_xs = [TL.REL_STAR1_X, TL.REL_STAR2_X, TL.REL_STAR3_X]
    for i, name in enumerate(["Star: 5 Points 22", "Star: 5 Points 24", "Star: 5 Points 25"]):
        shape = _find_shape_by_name(slide, name)
        if shape:
            _reposition_shape(shape, rel_star_xs[i], TL.REL_STARS_Y,
                              TL.STAR_SIZE, TL.STAR_SIZE)

    # Source URL
    shape = _find_shape_by_name(slide, "ZoneTexte 4")
    if shape:
        _reposition_shape(shape, TL.SOURCE_X, TL.SOURCE_Y,
                          TL.SOURCE_W, TL.SOURCE_H)

    # ── Image (Picture 15) — align top with content section ──

    shape = _find_shape_by_name(slide, "Picture 15")
    if shape:
        _reposition_shape(shape, TL.ARTICLE_IMG_X, TL.ARTICLE_IMG_Y,
                          TL.ARTICLE_IMG_W, TL.ARTICLE_IMG_H)


# ── XML builders ────────────────────────────────────────────────────────

def _enable_autofit(bodyPr):
    """Enable normAutofit on bodyPr so PowerPoint auto-shrinks text."""
    if bodyPr is None:
        return
    for tag in ["a:noAutofit", "a:normAutofit", "a:spAutoFit"]:
        old = bodyPr.find(qn(tag))
        if old is not None:
            bodyPr.remove(old)
    etree.SubElement(bodyPr, qn("a:normAutofit"))


def _make_run(text: str, font_size: int, lang: str = "en-US",
              bold: bool = False) -> etree._Element:
    """Create an <a:r> run element."""
    r = etree.Element(qn("a:r"))
    rPr = etree.SubElement(r, qn("a:rPr"))
    rPr.set("lang", lang)
    rPr.set("sz", str(font_size))
    rPr.set("dirty", "0")
    if bold:
        rPr.set("b", "1")
    solidFill = etree.SubElement(rPr, qn("a:solidFill"))
    schemeClr = etree.SubElement(solidFill, qn("a:schemeClr"))
    schemeClr.set("val", "tx1")
    t = etree.SubElement(r, qn("a:t"))
    t.text = text
    return r


def _make_paragraph(text: str, font_size: int, lang: str = "en-US",
                    space_before: int = 400) -> etree._Element:
    """Create a plain paragraph (no bullet)."""
    p = etree.Element(qn("a:p"))
    pPr = etree.SubElement(p, qn("a:pPr"))
    spcBef = etree.SubElement(pPr, qn("a:spcBef"))
    spcPts = etree.SubElement(spcBef, qn("a:spcPts"))
    spcPts.set("val", str(space_before))
    p.append(_make_run(text, font_size, lang))
    return p


def _make_bullet_paragraph(text: str, font_size: int, level: int = 0,
                           lang: str = "en-GB") -> etree._Element:
    """Create a bulleted paragraph. level=0 uses •, level=1 uses Wingdings Ø."""
    p = etree.Element(qn("a:p"))
    pPr = etree.SubElement(p, qn("a:pPr"))

    if level == 0:
        pPr.set("marL", "182563")
        pPr.set("indent", "-182563")
    else:
        pPr.set("marL", "446088")
        pPr.set("lvl", "1")
        pPr.set("indent", "-271463")

    spcBef = etree.SubElement(pPr, qn("a:spcBef"))
    spcPts = etree.SubElement(spcBef, qn("a:spcPts"))
    spcPts.set("val", "600")

    buFont = etree.SubElement(pPr, qn("a:buFont"))
    if level == 0:
        buFont.set("typeface", "Arial")
        buFont.set("panose", "020B0604020202020204")
        buFont.set("pitchFamily", "34")
        buFont.set("charset", "0")
        buChar = etree.SubElement(pPr, qn("a:buChar"))
        buChar.set("char", "\u2022")
    else:
        buFont.set("typeface", "Wingdings")
        buFont.set("panose", "05000000000000000000")
        buFont.set("pitchFamily", "2")
        buFont.set("charset", "2")
        buChar = etree.SubElement(pPr, qn("a:buChar"))
        buChar.set("char", "\u00D8")

    r = _make_run(text, font_size, lang)
    # Add altLang for sub-bullets (matches template)
    if level == 1:
        rPr = r.find(qn("a:rPr"))
        rPr.set("altLang", "ja-JP")
    p.append(r)
    return p


# ── Shape updaters ──────────────────────────────────────────────────────

def _update_title(slide, title: str):
    """Element 11: headline text in Titre 42."""
    shape = _find_shape_by_name(slide, "Titre 42")
    if not shape or not shape.has_text_frame:
        logger.warning("Could not find Titre 42")
        return

    # Truncate if excessively long
    if len(title) > TL.TITLE_MAX_CHARS:
        title = title[:TL.TITLE_MAX_CHARS - 3] + "..."

    txBody = shape._element.find(qn("p:txBody"))
    bodyPr = txBody.find(qn("a:bodyPr"))
    _enable_autofit(bodyPr)

    # Replace text in existing paragraph structure to preserve formatting
    for p in txBody.findall(qn("a:p")):
        for r in p.findall(qn("a:r")):
            t = r.find(qn("a:t"))
            if t is not None:
                t.text = title
                return
    # Fallback: build from scratch
    for p in txBody.findall(qn("a:p")):
        txBody.remove(p)
    p = etree.SubElement(txBody, qn("a:p"))
    r = _make_run(title, TL.TITLE_FONT_SIZE, bold=True)
    rPr = r.find(qn("a:rPr"))
    latin = etree.SubElement(rPr, qn("a:latin"))
    latin.set("typeface", "+mn-lt")
    p.append(r)


def _update_category(slide, category: str):
    """Element 2: category tag in Rectangle 5."""
    cat = category.upper().strip()
    if len(cat) > TL.CATEGORY_MAX_CHARS:
        cat = cat[:TL.CATEGORY_MAX_CHARS - 1] + "."

    shape = _find_shape_by_name(slide, "Rectangle 5")
    if not shape or not shape.has_text_frame:
        logger.warning("Could not find Rectangle 5")
        return

    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            run.text = cat
            return


def _update_date(slide, date_str: str):
    """Element 12: date in ZoneTexte 6."""
    shape = _find_shape_by_name(slide, "ZoneTexte 6")
    if not shape or not shape.has_text_frame:
        logger.warning("Could not find ZoneTexte 6")
        return

    for para in shape.text_frame.paragraphs:
        for run in para.runs:
            run.text = date_str
            return


def _update_summary(slide, summary: str, relevant_info: str):
    """Element 9: summary + relevant info in Rectangle 13.

    Text is plain paragraphs by default. No bullets unless the text
    explicitly contains sub-points (lines starting with "- ").
    Font size is selected based on total word count.
    """
    shape = _find_shape_by_name(slide, "Rectangle 13")
    if not shape:
        logger.warning("Could not find Rectangle 13")
        return

    txBody = shape._element.find(qn("p:txBody"))
    if txBody is None:
        return

    bodyPr = txBody.find(qn("a:bodyPr"))
    _enable_autofit(bodyPr)

    # Remove existing paragraphs
    for p in txBody.findall(qn("a:p")):
        txBody.remove(p)

    # Combine all text for font size calculation
    all_text = summary
    if relevant_info and relevant_info.strip() and not _is_error_text(relevant_info):
        all_text += " " + relevant_info
    font_size = _choose_font_size(all_text, TL.SUMMARY_FONT_SIZE, TL.SUMMARY_FONT_MIN)

    # Build summary paragraphs
    summary_lines = [l.strip() for l in summary.split("\n") if l.strip()]
    has_sub_points = any(l.startswith("- ") for l in summary_lines)

    if has_sub_points:
        for line in summary_lines:
            if line.startswith("- "):
                txBody.append(_make_bullet_paragraph(line[2:], font_size, level=0))
            else:
                txBody.append(_make_paragraph(line, font_size))
    else:
        for line in summary_lines:
            txBody.append(_make_paragraph(line, font_size))

    # Add relevant info if present
    if relevant_info and relevant_info.strip() and not _is_error_text(relevant_info):
        rel_lines = [l.strip() for l in relevant_info.split("\n") if l.strip()]
        has_rel_sub = any(l.startswith("- ") for l in rel_lines)

        if has_rel_sub:
            for line in rel_lines:
                if line.startswith("- "):
                    txBody.append(_make_bullet_paragraph(line[2:], font_size, level=0))
                else:
                    txBody.append(_make_paragraph(line, font_size))
        else:
            for line in rel_lines:
                txBody.append(_make_paragraph(line, font_size))


def _update_implications(slide, main_point: str, sub_points: list):
    """Element 10: implications in Rectangle 16.

    Main point is a plain paragraph. Sub-points get Wingdings Ø bullets
    ONLY if they exist. Font size is selected based on total word count.
    """
    shape = _find_shape_by_name(slide, "Rectangle 16")
    if not shape:
        logger.warning("Could not find Rectangle 16")
        return

    txBody = shape._element.find(qn("p:txBody"))
    if txBody is None:
        return

    bodyPr = txBody.find(qn("a:bodyPr"))
    _enable_autofit(bodyPr)

    # Remove existing paragraphs
    for p in txBody.findall(qn("a:p")):
        txBody.remove(p)

    # Calculate font size from total text
    all_text = main_point + " " + " ".join(sub_points)
    font_size = _choose_font_size(all_text, TL.IMPLICATIONS_FONT_SIZE, TL.IMPLICATIONS_FONT_MIN)

    # Main point — plain paragraph (no bullet)
    txBody.append(_make_paragraph(main_point, font_size, lang="en-GB", space_before=400))

    # Sub-points — Wingdings Ø bullets ONLY if sub_points exist
    for sub in sub_points:
        txBody.append(_make_bullet_paragraph(sub, font_size, level=1, lang="en-GB"))


def _update_source_url(slide, url: str):
    """Source URL with hyperlink in ZoneTexte 4."""
    shape = _find_shape_by_name(slide, "ZoneTexte 4")
    if not shape:
        logger.warning("Could not find ZoneTexte 4")
        return

    txBody = shape._element.find(qn("p:txBody"))
    if txBody is None:
        return

    for p in txBody.findall(qn("a:p")):
        txBody.remove(p)

    p = etree.SubElement(txBody, qn("a:p"))

    # "Source: " prefix
    r1 = etree.SubElement(p, qn("a:r"))
    rPr1 = etree.SubElement(r1, qn("a:rPr"))
    rPr1.set("lang", "fr-FR")
    rPr1.set("sz", str(TL.SOURCE_FONT_SIZE))
    rPr1.set("dirty", "0")
    latin1 = etree.SubElement(rPr1, qn("a:latin"))
    latin1.set("typeface", "+mj-lt")
    t1 = etree.SubElement(r1, qn("a:t"))
    t1.text = "Source: "

    # URL with hyperlink
    r2 = etree.SubElement(p, qn("a:r"))
    rPr2 = etree.SubElement(r2, qn("a:rPr"))
    rPr2.set("lang", "fr-FR")
    rPr2.set("sz", str(TL.SOURCE_FONT_SIZE))
    rPr2.set("dirty", "0")
    latin2 = etree.SubElement(rPr2, qn("a:latin"))
    latin2.set("typeface", "+mj-lt")

    rel = slide.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hlinkClick = etree.SubElement(rPr2, qn("a:hlinkClick"))
    hlinkClick.set(qn("r:id"), rel)

    t2 = etree.SubElement(r2, qn("a:t"))
    t2.text = url if len(url) <= 120 else url[:120] + "..."


def _set_star_color(shape, color_hex: str):
    spPr = shape._element.find(qn("p:spPr"))
    if spPr is None:
        return
    solidFill = spPr.find(qn("a:solidFill"))
    if solidFill is None:
        solidFill = etree.SubElement(spPr, qn("a:solidFill"))
    for child in list(solidFill):
        solidFill.remove(child)
    srgbClr = etree.SubElement(solidFill, qn("a:srgbClr"))
    srgbClr.set("val", color_hex)


def _update_stars(slide, credibility: float, relevance: float):
    """Elements 6 & 8: star ratings."""
    cred_n = score_to_stars(credibility)
    rel_n = score_to_stars(relevance)

    cred_names = ["Star: 5 Points 10", "Star: 5 Points 11", "Star: 5 Points 12"]
    for i, name in enumerate(cred_names):
        shape = _find_shape_by_name(slide, name)
        if shape:
            _set_star_color(shape, TL.STAR_FILLED if (i + 1) <= cred_n else TL.STAR_EMPTY)

    rel_names = ["Star: 5 Points 22", "Star: 5 Points 24", "Star: 5 Points 25"]
    for i, name in enumerate(rel_names):
        shape = _find_shape_by_name(slide, name)
        if shape:
            _set_star_color(shape, TL.STAR_FILLED if (i + 1) <= rel_n else TL.STAR_EMPTY)


# ── Image handling ──────────────────────────────────────────────────────

def _replace_article_image(slide, image_path: str, prs):
    """Replace the single article image (Picture 15) using two-boundary scaling."""
    if not image_path or not os.path.exists(image_path):
        _remove_pic_shape(slide, "Picture 15")
        return

    from PIL import Image as PILImage

    # Find Picture 15 to read its slot position and size
    spTree = slide._element.find(qn("p:cSld")).find(qn("p:spTree"))
    for pic_elem in spTree.findall(qn("p:pic")):
        nvPicPr = pic_elem.find(qn("p:nvPicPr"))
        if nvPicPr is None:
            continue
        cNvPr = nvPicPr.find(qn("p:cNvPr"))
        if cNvPr is None or cNvPr.get("name") != "Picture 15":
            continue

        spPr = pic_elem.find(qn("p:spPr"))
        if spPr is None:
            break
        xfrm = spPr.find(qn("a:xfrm"))
        if xfrm is None:
            break
        off = xfrm.find(qn("a:off"))
        ext = xfrm.find(qn("a:ext"))
        if off is None or ext is None:
            break

        slot_left = int(off.get("x", 0))
        slot_top = int(off.get("y", 0))
        outer_w = int(ext.get("cx", 0))
        outer_h = int(ext.get("cy", 0))
        if outer_w == 0 or outer_h == 0:
            break

        # Remove the placeholder shape
        spTree.remove(pic_elem)

        # Get image pixel dimensions
        try:
            with PILImage.open(image_path) as img:
                img_w, img_h = img.size
        except Exception as e:
            logger.warning(f"Could not read image dimensions: {e}")
            return

        # Inner boundary = 88% of outer (soft minimum)
        inner_w = int(outer_w * 0.88)
        inner_h = int(outer_h * 0.88)

        # Two-boundary scaling
        scale_outer = min(outer_w / img_w, outer_h / img_h)
        scale_inner = max(inner_w / img_w, inner_h / img_h)
        scale = min(scale_outer, max(scale_inner, 1e-6))

        new_w = int(img_w * scale)
        new_h = int(img_h * scale)

        # Center inside outer box
        left_offset = slot_left + int((outer_w - new_w) / 2)
        top_offset = slot_top + int((outer_h - new_h) / 2)

        slide.shapes.add_picture(
            image_path,
            left_offset,
            top_offset,
            width=Emu(new_w),
            height=Emu(new_h),
        )
        logger.info("Replaced article image (two-boundary scaled)")
        return

    logger.warning("Could not find Picture 15 for image replacement")


def _remove_pic_shape(slide, shape_name: str):
    spTree = slide._element.find(qn("p:cSld")).find(qn("p:spTree"))
    for pic_elem in spTree.findall(qn("p:pic")):
        nvPicPr = pic_elem.find(qn("p:nvPicPr"))
        if nvPicPr is not None:
            cNvPr = nvPicPr.find(qn("p:cNvPr"))
            if cNvPr is not None and cNvPr.get("name") == shape_name:
                spTree.remove(pic_elem)
                logger.info(f"Removed image shape: {shape_name}")
                return




# ── Main generation ─────────────────────────────────────────────────────

def generate_slide(article: ArticleData, output_filename: str = None) -> Optional[str]:
    """Generate a single slide from article data.

    Returns path to the generated .pptx file, or None on failure.
    """
    try:
        article = _sanitize(article)
        prs = Presentation(str(TEMPLATE_PATH))

        # Keep only slide 1
        slide_ids = prs.slides._sldIdLst
        while len(slide_ids) > 1:
            rId = slide_ids[-1].get(qn("r:id"))
            prs.part.drop_rel(rId)
            slide_ids.remove(slide_ids[-1])

        slide = prs.slides[0]

        # 0. Apply grid layout (reposition + visual hierarchy)
        _apply_grid_layout(slide)

        # 1. Title (Element 11)
        _update_title(slide, article.title)

        # 2. Category (Element 2)
        _update_category(slide, article.category)

        # 3. Date (Element 12)
        _update_date(slide, _format_date(article.publication_date))

        # 4. Summary + Relevant Info (Element 9)
        _update_summary(slide, article.summary, article.relevant_info)

        # 5. Implications (Element 10)
        if article.implications and article.implications.strip():
            _update_implications(slide, article.implications,
                                 article.implications_sub or [])

        # 6. Source URL
        if article.source_url:
            _update_source_url(slide, article.source_url)

        # 7. Stars (Elements 6 & 8)
        _update_stars(slide, article.credibility_score, article.relevancy_score)

        # 8. Article image
        _replace_article_image(slide, article.article_image, prs)

        # Save
        if not output_filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe = "".join(c for c in article.title[:40] if c.isalnum() or c in " -_").strip()
            safe = safe.replace(" ", "_")
            output_filename = f"article_{ts}_{safe}.pptx"

        output_path = SLIDES_DIR / output_filename
        prs.save(str(output_path))
        logger.info(f"Slide saved: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"Slide generation failed: {e}", exc_info=True)
        return None


def generate_slide_from_notion_data(notion_data: dict,
                                     image_paths: dict = None) -> Optional[str]:
    """Generate a slide from raw Notion data dict.

    Args:
        notion_data: Dict with Notion field values.
        image_paths: Dict with optional key "article" pointing to image path.
                     Also accepts legacy keys "main", "byline", etc.
    """
    images = image_paths or {}

    # Parse implications: first line = main point, rest = sub-bullets
    impl_raw = notion_data.get("implications", "")
    impl_lines = [l.strip() for l in impl_raw.split("\n") if l.strip()]
    main_impl = impl_lines[0] if impl_lines else impl_raw
    sub_impl = impl_lines[1:] if len(impl_lines) > 1 else []

    # Resolve image: prefer "article" key, fall back to "main"
    article_img = images.get("article") or images.get("main")

    article = ArticleData(
        title=notion_data.get("title", "Untitled Article"),
        summary=notion_data.get("summary", ""),
        relevant_info=notion_data.get("relevant_info", ""),
        implications=main_impl,
        implications_sub=sub_impl,
        category=notion_data.get("category", "GENERAL INNOVATION"),
        publication_date=notion_data.get("publication_date", ""),
        source_url=notion_data.get("source_url", ""),
        source_name=notion_data.get("source_name", ""),
        credibility_score=float(notion_data.get("credibility_score", 3.0)),
        relevancy_score=float(notion_data.get("relevancy_score", 3.0)),
        article_image=article_img,
    )

    return generate_slide(article)
