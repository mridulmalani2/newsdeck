"""
PPTX Generator Module - Creates slides from article data using the template.

Uses python-pptx to clone slide 1 from the template and replace all dynamic content:
- Title (headline)
- Category tag
- Date
- Summary bullets
- Implications bullets (with sub-bullets)
- Source URL (with hyperlink)
- Credibility/Relevancy star ratings (3-star scale)
- Left-side article images (from Playwright captures)
"""

import copy
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn, nsmap
from lxml import etree

from config import TemplateLayout as TL, TEMPLATE_PATH, SLIDES_DIR


def _format_date(date_str: str) -> str:
    """Normalize date to DD/MM/YYYY format."""
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

logger = logging.getLogger(__name__)

# Patterns that indicate error/system text from upstream AI evaluation
_ERROR_INDICATORS = [
    "parsing failed",
    "evaluation parsing failed",
    "using default scores",
    "failed to",
    "error:",
    "exception:",
    "traceback",
    "no data available",
    "could not parse",
    "api error",
]


def _is_error_text(text: str) -> bool:
    """Check if text looks like an error message from upstream AI evaluation."""
    if not text:
        return False
    text_lower = text.lower().strip()
    return any(indicator in text_lower for indicator in _ERROR_INDICATORS)


def _sanitize_article(article: 'ArticleData') -> 'ArticleData':
    """Clean article data by filtering out error messages from upstream AI eval."""
    # Filter relevant_info if it contains error text
    if _is_error_text(article.relevant_info):
        logger.warning(f"Filtered error text from relevant_info: {article.relevant_info[:80]}")
        article.relevant_info = ""

    # Filter summary lines that are error messages
    if article.summary:
        lines = article.summary.split('\n')
        clean_lines = [l for l in lines if not _is_error_text(l)]
        article.summary = '\n'.join(clean_lines)

    # Filter implications if error text
    if _is_error_text(article.implications):
        logger.warning(f"Filtered error text from implications: {article.implications[:80]}")
        article.implications = ""

    # Filter sub-implications
    if article.implications_sub:
        article.implications_sub = [s for s in article.implications_sub if not _is_error_text(s)]

    return article


@dataclass
class ArticleData:
    """Data structure for a single article to be turned into a slide."""
    title: str = ""
    summary: str = ""
    relevant_info: str = ""
    implications: str = ""  # Main implication point
    implications_sub: list = field(default_factory=list)  # Sub-bullet implications
    category: str = "GENERAL INNOVATION"
    publication_date: str = ""  # DD/MM/YYYY
    source_url: str = ""
    source_name: str = ""
    credibility_score: float = 3.0  # 0-5
    relevancy_score: float = 3.0   # 0-5
    # Image paths (from Playwright capture)
    byline_image: Optional[str] = None
    headline_image: Optional[str] = None
    main_image: Optional[str] = None
    secondary_image: Optional[str] = None
    footer_image: Optional[str] = None


def score_to_stars(score: float, max_stars: int = 3) -> int:
    """Convert a 0-5 numeric score to a star count (out of max_stars).

    Mapping for 3-star scale:
      0.0 - 1.7  → 1 star
      1.8 - 3.3  → 2 stars
      3.4 - 5.0  → 3 stars
    """
    if score <= 1.7:
        return 1
    elif score <= 3.3:
        return 2
    else:
        return 3


def _find_shape_by_name(slide, name: str):
    """Find a shape in slide by its name attribute."""
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    return None


def _find_shape_by_id(slide, shape_id: int):
    """Find a shape in slide by its id."""
    for shape in slide.shapes:
        if shape.shape_id == shape_id:
            return shape
    return None


def _set_star_color(shape, color_hex: str):
    """Set the fill color of a star shape."""
    spPr = shape._element.find(qn('p:spPr'))
    if spPr is None:
        return
    solidFill = spPr.find(qn('a:solidFill'))
    if solidFill is None:
        solidFill = etree.SubElement(spPr, qn('a:solidFill'))
    # Clear existing color children
    for child in list(solidFill):
        solidFill.remove(child)
    srgbClr = etree.SubElement(solidFill, qn('a:srgbClr'))
    srgbClr.set('val', color_hex)


def _set_text_content(text_frame, text: str, font_size: int = 1400,
                       bold: bool = False, color_hex: str = None):
    """Set simple text content in a text frame, replacing all existing text."""
    for para in list(text_frame.paragraphs):
        for run in list(para.runs):
            run.text = ""
    if text_frame.paragraphs:
        p = text_frame.paragraphs[0]
        if p.runs:
            p.runs[0].text = text
        else:
            run = p.add_run()
            run.text = text


def _build_bullet_paragraphs_xml(items: list, font_size: int = 1400,
                                   lang: str = "en-US") -> list:
    """Build XML paragraph elements for bullet points matching template style."""
    paragraphs = []
    for item in items:
        p = etree.Element(qn('a:p'))
        pPr = etree.SubElement(p, qn('a:pPr'))
        pPr.set('marL', '182563')
        pPr.set('indent', '-182563')

        spcBef = etree.SubElement(pPr, qn('a:spcBef'))
        spcPts = etree.SubElement(spcBef, qn('a:spcPts'))
        spcPts.set('val', '600')

        buFont = etree.SubElement(pPr, qn('a:buFont'))
        buFont.set('typeface', 'Arial')
        buFont.set('panose', '020B0604020202020204')
        buFont.set('pitchFamily', '34')
        buFont.set('charset', '0')

        buChar = etree.SubElement(pPr, qn('a:buChar'))
        buChar.set('char', '\u2022')

        r = etree.SubElement(p, qn('a:r'))
        rPr = etree.SubElement(r, qn('a:rPr'))
        rPr.set('lang', lang)
        rPr.set('sz', str(font_size))
        rPr.set('dirty', '0')

        solidFill = etree.SubElement(rPr, qn('a:solidFill'))
        schemeClr = etree.SubElement(solidFill, qn('a:schemeClr'))
        schemeClr.set('val', 'tx1')

        t = etree.SubElement(r, qn('a:t'))
        t.text = item

        paragraphs.append(p)
    return paragraphs


def _build_implications_xml(main_point: str, sub_points: list,
                              font_size: int = 1400) -> list:
    """Build implications XML with main bullet + Wingdings sub-bullets."""
    paragraphs = []

    # Main bullet
    p = etree.Element(qn('a:p'))
    pPr = etree.SubElement(p, qn('a:pPr'))
    pPr.set('marL', '182563')
    pPr.set('indent', '-182563')

    spcBef = etree.SubElement(pPr, qn('a:spcBef'))
    spcPts = etree.SubElement(spcBef, qn('a:spcPts'))
    spcPts.set('val', '600')

    buFont = etree.SubElement(pPr, qn('a:buFont'))
    buFont.set('typeface', 'Arial')
    buFont.set('panose', '020B0604020202020204')
    buFont.set('pitchFamily', '34')
    buFont.set('charset', '0')

    buChar = etree.SubElement(pPr, qn('a:buChar'))
    buChar.set('char', '\u2022')

    r = etree.SubElement(p, qn('a:r'))
    rPr = etree.SubElement(r, qn('a:rPr'))
    rPr.set('lang', 'en-GB')
    rPr.set('sz', str(font_size))
    rPr.set('dirty', '0')
    solidFill = etree.SubElement(rPr, qn('a:solidFill'))
    schemeClr = etree.SubElement(solidFill, qn('a:schemeClr'))
    schemeClr.set('val', 'tx1')
    t = etree.SubElement(r, qn('a:t'))
    t.text = main_point

    paragraphs.append(p)

    # Sub-bullets with Wingdings Ø
    for sub in sub_points:
        p = etree.Element(qn('a:p'))
        pPr = etree.SubElement(p, qn('a:pPr'))
        pPr.set('marL', '446088')
        pPr.set('lvl', '1')
        pPr.set('indent', '-271463')

        spcBef = etree.SubElement(pPr, qn('a:spcBef'))
        spcPts = etree.SubElement(spcBef, qn('a:spcPts'))
        spcPts.set('val', '600')

        buFont = etree.SubElement(pPr, qn('a:buFont'))
        buFont.set('typeface', 'Wingdings')
        buFont.set('panose', '05000000000000000000')
        buFont.set('pitchFamily', '2')
        buFont.set('charset', '2')

        buChar = etree.SubElement(pPr, qn('a:buChar'))
        buChar.set('char', '\u00D8')  # Ø in Wingdings

        r = etree.SubElement(p, qn('a:r'))
        rPr = etree.SubElement(r, qn('a:rPr'))
        rPr.set('lang', 'en-GB')
        rPr.set('altLang', 'ja-JP')
        rPr.set('sz', str(font_size))
        rPr.set('dirty', '0')
        solidFill = etree.SubElement(rPr, qn('a:solidFill'))
        schemeClr = etree.SubElement(solidFill, qn('a:schemeClr'))
        schemeClr.set('val', 'tx1')
        t = etree.SubElement(r, qn('a:t'))
        t.text = sub

        paragraphs.append(p)

    return paragraphs


def _replace_image(slide, shape_name: str, image_path: str, prs: Presentation):
    """Replace an image in the slide by finding the pic element and swapping the blip."""
    if not image_path or not os.path.exists(image_path):
        logger.warning(f"Image not found for {shape_name}: {image_path}")
        return False

    # Find the pic element by name in raw XML
    spTree = slide._element.find(qn('p:cSld')).find(qn('p:spTree'))
    for pic_elem in spTree.findall(qn('p:pic')):
        nvPicPr = pic_elem.find(qn('p:nvPicPr'))
        if nvPicPr is not None:
            cNvPr = nvPicPr.find(qn('p:cNvPr'))
            if cNvPr is not None and cNvPr.get('name') == shape_name:
                # Found the target pic element
                blipFill = pic_elem.find(qn('p:blipFill'))
                if blipFill is not None:
                    blip = blipFill.find(qn('a:blip'))
                    if blip is not None:
                        # Add the new image to the presentation
                        rel = slide.part.relate_to(
                            prs.part._package.get_or_add_image_part(image_path),
                            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
                        )
                        blip.set(qn('r:embed'), rel)
                        logger.info(f"Replaced image for {shape_name}")
                        return True

    logger.warning(f"Could not find pic element: {shape_name}")
    return False


def _replace_image_by_id(slide, shape_id: int, image_path: str, prs: Presentation):
    """Replace an image by shape ID."""
    if not image_path or not os.path.exists(image_path):
        return False

    spTree = slide._element.find(qn('p:cSld')).find(qn('p:spTree'))
    for pic_elem in spTree.findall(qn('p:pic')):
        nvPicPr = pic_elem.find(qn('p:nvPicPr'))
        if nvPicPr is not None:
            cNvPr = nvPicPr.find(qn('p:cNvPr'))
            if cNvPr is not None and cNvPr.get('id') == str(shape_id):
                blipFill = pic_elem.find(qn('p:blipFill'))
                if blipFill is not None:
                    blip = blipFill.find(qn('a:blip'))
                    if blip is not None:
                        rel = slide.part.relate_to(
                            prs.part._package.get_or_add_image_part(image_path),
                            "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
                        )
                        blip.set(qn('r:embed'), rel)
                        return True
    return False


def _update_text_by_shape_name(slide, shape_name: str, new_text: str):
    """Update text content of a shape found by name."""
    shape = _find_shape_by_name(slide, shape_name)
    if shape and shape.has_text_frame:
        tf = shape.text_frame
        if tf.paragraphs and tf.paragraphs[0].runs:
            tf.paragraphs[0].runs[0].text = new_text
            return True
    return False


def _update_category_tag(slide, category: str):
    """Update the category tag text (Rectangle 5)."""
    shape = _find_shape_by_name(slide, "Rectangle 5")
    if shape and shape.has_text_frame:
        tf = shape.text_frame
        for para in tf.paragraphs:
            for run in para.runs:
                run.text = category.upper()
        return True
    return False


def _update_title(slide, title: str):
    """Update the title text (Titre 42)."""
    shape = _find_shape_by_name(slide, "Titre 42")
    if shape and shape.has_text_frame:
        tf = shape.text_frame
        for para in tf.paragraphs:
            for run in para.runs:
                run.text = title
        return True
    return False


def _update_date(slide, date_str: str):
    """Update the date text box (ZoneTexte 6)."""
    shape = _find_shape_by_name(slide, "ZoneTexte 6")
    if shape and shape.has_text_frame:
        tf = shape.text_frame
        for para in tf.paragraphs:
            for run in para.runs:
                run.text = date_str
        return True
    return False


def _update_summary(slide, summary_points: list, relevant_info: str = ""):
    """Update the summary text box (Rectangle 13) with bullet points."""
    shape = _find_shape_by_name(slide, "Rectangle 13")
    if not shape:
        logger.warning("Could not find Rectangle 13 (summary text box)")
        return False

    txBody = shape._element.find(qn('p:txBody'))
    if txBody is None:
        return False

    # Remove existing paragraphs (keep bodyPr and lstStyle)
    bodyPr = txBody.find(qn('a:bodyPr'))
    lstStyle = txBody.find(qn('a:lstStyle'))
    for p in txBody.findall(qn('a:p')):
        txBody.remove(p)

    # Add summary bullet points
    for para_elem in _build_bullet_paragraphs_xml(summary_points):
        txBody.append(para_elem)

    # Add separator + relevant info ONLY if relevant_info has valid content
    if relevant_info and relevant_info.strip() and not _is_error_text(relevant_info):
        # Separator line
        sep_p = etree.SubElement(txBody, qn('a:p'))
        sep_pPr = etree.SubElement(sep_p, qn('a:pPr'))
        spcBef = etree.SubElement(sep_pPr, qn('a:spcBef'))
        spcPts = etree.SubElement(spcBef, qn('a:spcPts'))
        spcPts.set('val', '600')
        sep_r = etree.SubElement(sep_p, qn('a:r'))
        sep_rPr = etree.SubElement(sep_r, qn('a:rPr'))
        sep_rPr.set('lang', 'en-GB')
        sep_rPr.set('altLang', 'ja-JP')
        sep_rPr.set('sz', '1400')
        sep_rPr.set('dirty', '0')
        solidFill = etree.SubElement(sep_rPr, qn('a:solidFill'))
        schemeClr = etree.SubElement(solidFill, qn('a:schemeClr'))
        schemeClr.set('val', 'tx1')
        sep_t = etree.SubElement(sep_r, qn('a:t'))
        sep_t.text = "----- relevant Information -----"

        # Relevant info bullets
        rel_items = [relevant_info] if isinstance(relevant_info, str) else relevant_info
        for para_elem in _build_bullet_paragraphs_xml(rel_items, lang="fr-FR"):
            txBody.append(para_elem)

    return True


def _update_implications(slide, main_point: str, sub_points: list):
    """Update the implications text box (Rectangle 16) with hierarchical bullets."""
    shape = _find_shape_by_name(slide, "Rectangle 16")
    if not shape:
        logger.warning("Could not find Rectangle 16 (implications text box)")
        return False

    txBody = shape._element.find(qn('p:txBody'))
    if txBody is None:
        return False

    # Remove existing paragraphs
    for p in txBody.findall(qn('a:p')):
        txBody.remove(p)

    # Add implications with hierarchy
    for para_elem in _build_implications_xml(main_point, sub_points):
        txBody.append(para_elem)

    return True


def _update_source_url(slide, url: str):
    """Update the source URL text box (ZoneTexte 4) with hyperlink."""
    shape = _find_shape_by_name(slide, "ZoneTexte 4")
    if not shape:
        logger.warning("Could not find ZoneTexte 4 (source URL box)")
        return False

    txBody = shape._element.find(qn('p:txBody'))
    if txBody is None:
        return False

    # Remove existing paragraphs
    for p in txBody.findall(qn('a:p')):
        txBody.remove(p)

    # Build new paragraph with "Source: " prefix and hyperlinked URL
    p = etree.SubElement(txBody, qn('a:p'))

    # "Source: " run
    r1 = etree.SubElement(p, qn('a:r'))
    rPr1 = etree.SubElement(r1, qn('a:rPr'))
    rPr1.set('lang', 'fr-FR')
    rPr1.set('sz', '1000')
    rPr1.set('b', '0')
    rPr1.set('i', '0')
    rPr1.set('strike', 'noStrike')
    rPr1.set('dirty', '0')
    latin1 = etree.SubElement(rPr1, qn('a:latin'))
    latin1.set('typeface', '+mj-lt')
    t1 = etree.SubElement(r1, qn('a:t'))
    t1.text = "Source: "

    # URL run with hyperlink
    r2 = etree.SubElement(p, qn('a:r'))
    rPr2 = etree.SubElement(r2, qn('a:rPr'))
    rPr2.set('lang', 'fr-FR')
    rPr2.set('sz', '1000')
    rPr2.set('b', '0')
    rPr2.set('i', '0')
    rPr2.set('strike', 'noStrike')
    rPr2.set('dirty', '0')
    latin2 = etree.SubElement(rPr2, qn('a:latin'))
    latin2.set('typeface', '+mj-lt')

    # Add hyperlink relationship
    rel = slide.part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True
    )
    hlinkClick = etree.SubElement(rPr2, qn('a:hlinkClick'))
    hlinkClick.set(qn('r:id'), rel)

    t2 = etree.SubElement(r2, qn('a:t'))
    t2.text = url

    return True


def _update_stars(slide, credibility_score: float, relevancy_score: float):
    """Update star ratings for credibility and relevancy.

    Stars are individual shape elements named 'Star: 5 Points N'.
    Credibility stars: IDs 11, 12, 13 (shapes 10, 11, 12)
    Relevancy stars:  IDs 23, 25, 26 (shapes 22, 24, 25)
    """
    cred_stars = score_to_stars(credibility_score)
    rel_stars = score_to_stars(relevancy_score)

    # Credibility stars (names from template)
    cred_star_names = ["Star: 5 Points 10", "Star: 5 Points 11", "Star: 5 Points 12"]
    for i, name in enumerate(cred_star_names):
        shape = _find_shape_by_name(slide, name)
        if shape:
            color = TL.STAR_FILLED if (i + 1) <= cred_stars else TL.STAR_EMPTY
            _set_star_color(shape, color)

    # Relevancy stars
    rel_star_names = ["Star: 5 Points 22", "Star: 5 Points 24", "Star: 5 Points 25"]
    for i, name in enumerate(rel_star_names):
        shape = _find_shape_by_name(slide, name)
        if shape:
            color = TL.STAR_FILLED if (i + 1) <= rel_stars else TL.STAR_EMPTY
            _set_star_color(shape, color)


def generate_slide(article: ArticleData, output_filename: str = None) -> Optional[str]:
    """Generate a single slide from article data using the template.

    Args:
        article: ArticleData with all fields populated
        output_filename: Optional custom filename; auto-generated if None

    Returns:
        Path to the generated .pptx file, or None on failure
    """
    try:
        # Sanitize article data — filter out error messages from upstream AI eval
        article = _sanitize_article(article)

        # Load template
        prs = Presentation(str(TEMPLATE_PATH))

        # We work with slide 1 (index 0) as the template
        # Keep only the first slide, remove others
        slide_ids = prs.slides._sldIdLst
        while len(slide_ids) > 1:
            # Remove last slide
            rId = slide_ids[-1].get(qn('r:id'))
            prs.part.drop_rel(rId)
            slide_ids.remove(slide_ids[-1])

        slide = prs.slides[0]

        # 1. Update title
        _update_title(slide, article.title)
        logger.info(f"Updated title: {article.title[:50]}...")

        # 2. Update category tag
        _update_category_tag(slide, article.category)
        logger.info(f"Updated category: {article.category}")

        # 3. Update date
        date_str = _format_date(article.publication_date)
        _update_date(slide, date_str)
        logger.info(f"Updated date: {date_str}")

        # 4. Update summary with bullets
        summary_points = [s.strip() for s in article.summary.split('\n') if s.strip()]
        if not summary_points:
            summary_points = [article.summary]
        _update_summary(slide, summary_points, article.relevant_info)
        logger.info("Updated summary text")

        # 5. Update implications (only if we have valid content)
        if article.implications and article.implications.strip():
            impl_sub = article.implications_sub or []
            _update_implications(slide, article.implications, impl_sub)
            logger.info("Updated implications text")
        else:
            logger.warning("No valid implications text — leaving template default")

        # 6. Update source URL
        if article.source_url:
            _update_source_url(slide, article.source_url)
            logger.info(f"Updated source URL: {article.source_url[:60]}...")

        # 7. Update star ratings
        _update_stars(slide, article.credibility_score, article.relevancy_score)
        logger.info(f"Updated stars: cred={article.credibility_score}, rel={article.relevancy_score}")

        # 8. Replace images if available
        # Map: (shape_name_pattern, image_path)
        # The template image shapes have Japanese names like "図 3", "図 4", etc.
        image_mappings = [
            ("図 3", article.byline_image),       # Publication logo
            ("図 4", article.headline_image),      # Headline screenshot
            ("図 17", article.main_image),         # Main article image (top)
            ("図 26", article.secondary_image),    # Secondary image (bottom)
            ("図 19", article.footer_image),       # Footer screenshot
        ]

        for shape_name, img_path in image_mappings:
            if img_path and os.path.exists(img_path):
                _replace_image(slide, shape_name, img_path, prs)
                logger.info(f"Replaced image: {shape_name}")

        # Generate output filename
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in article.title[:40] if c.isalnum() or c in " -_").strip()
            safe_title = safe_title.replace(" ", "_")
            output_filename = f"article_{timestamp}_{safe_title}.pptx"

        output_path = SLIDES_DIR / output_filename
        prs.save(str(output_path))
        logger.info(f"Slide saved to: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to generate slide: {e}", exc_info=True)
        return None


def generate_slide_from_notion_data(notion_data: dict,
                                     image_paths: dict = None) -> Optional[str]:
    """Convenience function to generate a slide from raw Notion database fields.

    Args:
        notion_data: Dict with keys matching Notion field names
        image_paths: Dict with keys: byline, headline, main, secondary, footer

    Returns:
        Path to generated .pptx file
    """
    images = image_paths or {}

    # Parse implications into main + sub-bullets
    implications_raw = notion_data.get("implications", "")
    impl_lines = [l.strip() for l in implications_raw.split('\n') if l.strip()]
    main_impl = impl_lines[0] if impl_lines else implications_raw
    sub_impl = impl_lines[1:] if len(impl_lines) > 1 else []

    # Parse summary - split on common delimiters
    summary_raw = notion_data.get("summary", "")

    article = ArticleData(
        title=notion_data.get("title", "Untitled Article"),
        summary=summary_raw,
        relevant_info=notion_data.get("relevant_info", ""),
        implications=main_impl,
        implications_sub=sub_impl,
        category=notion_data.get("category", "GENERAL INNOVATION"),
        publication_date=notion_data.get("publication_date", ""),
        source_url=notion_data.get("source_url", ""),
        source_name=notion_data.get("source_name", ""),
        credibility_score=float(notion_data.get("credibility_score", 3.0)),
        relevancy_score=float(notion_data.get("relevancy_score", 3.0)),
        byline_image=images.get("byline"),
        headline_image=images.get("headline"),
        main_image=images.get("main"),
        secondary_image=images.get("secondary"),
        footer_image=images.get("footer"),
    )

    return generate_slide(article)
