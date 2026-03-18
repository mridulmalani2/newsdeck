"""
Slide Validator — Post-generation quality checks.

Runs after a slide is generated and returns a list of human-readable
issue strings.  These get written to the Notion "Comments" column so
the team can triage without opening every .pptx.

Checks performed:
  1. Missing article image
  2. Text overspill risk (summary/implications word count vs. hard limit)
  3. Missing required fields (title, summary, implications)
  4. Title truncation warning
  5. Category truncation warning
  6. Empty date (defaulted to today)
  7. Captured image contains cookie banner / Cloudflare page
  8. Missing source URL
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

from config import TemplateLayout as TL

logger = logging.getLogger(__name__)

# Hard word limits before text physically can't fit even at minimum font
SUMMARY_HARD_LIMIT = 220
IMPLICATIONS_HARD_LIMIT = 220


def validate_article(article_data: dict, image_paths: dict = None,
                     slide_path: str = None) -> List[str]:
    """Run all quality checks on an article and its generated slide.

    Args:
        article_data: Normalized article dict from Notion
        image_paths: Dict of captured image paths (may be None/empty)
        slide_path: Path to the generated .pptx file

    Returns:
        List of issue strings. Empty list = all checks passed.
    """
    issues: List[str] = []
    images = image_paths or {}

    # ── 1. Missing article image ──────────────────────────────────────
    article_img = images.get("article") or images.get("main")
    if not article_img or not os.path.exists(str(article_img)):
        source_url = article_data.get("source_url", "")
        if source_url:
            issues.append("Image: No article screenshot captured (URL was provided)")
        else:
            issues.append("Image: No source URL provided — no screenshot taken")

    # ── 2. Captured image quality check ───────────────────────────────
    if article_img and os.path.exists(str(article_img)):
        img_issues = _check_captured_image(str(article_img))
        issues.extend(img_issues)

    # ── 3. Missing required fields ────────────────────────────────────
    title = article_data.get("title", "").strip()
    summary = article_data.get("summary", "").strip()
    implications = article_data.get("implications", "").strip()

    if not title or title == "Untitled":
        issues.append("Field: Title is missing or empty")

    if not summary:
        issues.append("Field: Summary is empty — slide text box will be blank")

    if not implications:
        issues.append("Field: Implications is empty — slide text box will be blank")

    # ── 4. Text overspill risk ────────────────────────────────────────
    relevant_info = article_data.get("relevant_info", "").strip()
    summary_combined = summary
    if relevant_info:
        summary_combined += " " + relevant_info
    summary_wc = len(summary_combined.split())

    if summary_wc > SUMMARY_HARD_LIMIT:
        issues.append(
            f"Overspill: Summary+RelevantInfo is {summary_wc} words "
            f"(hard limit {SUMMARY_HARD_LIMIT}) — text will overflow even at 10pt"
        )
    elif summary_wc > TL.SUMMARY_MAX_WORDS:
        issues.append(
            f"Warning: Summary+RelevantInfo is {summary_wc} words "
            f"(recommended {TL.SUMMARY_MAX_WORDS}) — font reduced to fit"
        )

    impl_wc = len(implications.split()) if implications else 0
    if impl_wc > IMPLICATIONS_HARD_LIMIT:
        issues.append(
            f"Overspill: Implications is {impl_wc} words "
            f"(hard limit {IMPLICATIONS_HARD_LIMIT}) — text will overflow even at 10pt"
        )
    elif impl_wc > TL.IMPLICATIONS_MAX_WORDS:
        issues.append(
            f"Warning: Implications is {impl_wc} words "
            f"(recommended {TL.IMPLICATIONS_MAX_WORDS}) — font reduced to fit"
        )

    # ── 5. Title truncation ───────────────────────────────────────────
    if title and len(title) > TL.TITLE_MAX_CHARS:
        issues.append(
            f"Truncated: Title is {len(title)} chars "
            f"(max {TL.TITLE_MAX_CHARS}) — truncated with '...'"
        )

    # ── 6. Category truncation ────────────────────────────────────────
    category = article_data.get("category", "").strip()
    if category and len(category) > TL.CATEGORY_MAX_CHARS:
        issues.append(
            f"Truncated: Category '{category}' is {len(category)} chars "
            f"(max {TL.CATEGORY_MAX_CHARS}) — truncated"
        )

    # ── 7. Empty date ─────────────────────────────────────────────────
    pub_date = article_data.get("publication_date", "").strip()
    if not pub_date:
        issues.append("Date: Publication date missing — defaulted to today's date")

    # ── 8. Missing source URL ─────────────────────────────────────────
    source_url = article_data.get("source_url", "").strip()
    if not source_url:
        issues.append("Source: No source URL provided")

    # ── 9. Slide file check ───────────────────────────────────────────
    if slide_path and not os.path.exists(slide_path):
        issues.append("File: Generated slide file not found on disk")

    return issues


def _check_captured_image(image_path: str) -> List[str]:
    """Analyze captured screenshot for quality issues.

    Detects:
    - Suspiciously small images (likely failed capture)
    - Images that are mostly a single color (likely Cloudflare/blank page)
    """
    issues = []
    try:
        file_size = os.path.getsize(image_path)

        # Very small file = likely failed capture
        if file_size < 5000:  # <5KB
            issues.append(
                "Image: Captured screenshot is suspiciously small "
                f"({file_size} bytes) — may be a blank or error page"
            )
            return issues

        # Check image content for Cloudflare/cookie patterns
        try:
            from PIL import Image
            import statistics

            with Image.open(image_path) as img:
                # Resize to small sample for fast analysis
                sample = img.resize((100, 100)).convert("RGB")
                pixels = list(sample.getdata())

                # Check color variance — very low variance = single color page
                r_vals = [p[0] for p in pixels]
                g_vals = [p[1] for p in pixels]
                b_vals = [p[2] for p in pixels]

                r_var = statistics.variance(r_vals) if len(r_vals) > 1 else 0
                g_var = statistics.variance(g_vals) if len(g_vals) > 1 else 0
                b_var = statistics.variance(b_vals) if len(b_vals) > 1 else 0

                total_var = r_var + g_var + b_var

                if total_var < 100:
                    issues.append(
                        "Image: Screenshot appears to be mostly a single color "
                        "— likely a Cloudflare challenge or blank page"
                    )

                # Check if the image is predominantly white (>90% white pixels)
                white_count = sum(
                    1 for p in pixels
                    if p[0] > 240 and p[1] > 240 and p[2] > 240
                )
                white_pct = white_count / len(pixels) * 100
                if white_pct > 90:
                    issues.append(
                        f"Image: Screenshot is {white_pct:.0f}% white "
                        "— may be a failed capture or mostly-empty page"
                    )

        except ImportError:
            pass  # PIL not available — skip image analysis

    except Exception as e:
        logger.warning(f"Image quality check failed: {e}")

    return issues


def format_comments(issues: List[str]) -> str:
    """Format a list of issues into a single Comments string for Notion.

    Returns empty string if no issues (= clean slide).
    """
    if not issues:
        return ""

    lines = [f"• {issue}" for issue in issues]
    return "\n".join(lines)
