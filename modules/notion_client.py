"""
Notion Client Module - Reads article data from and writes back to Notion database.

Handles:
- Extracting article fields from webhook payload
- Querying the database for unprocessed articles
- Updating rows with slide links and generated flags
"""

import logging
from datetime import datetime
from typing import Optional, Dict, List

import httpx

from config import NOTION_API_KEY, NOTION_DATABASE_ID

logger = logging.getLogger(__name__)

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Error indicators from upstream AI evaluation
_EVAL_ERROR_PATTERNS = [
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


def _is_evaluation_error(text: str) -> bool:
    """Check if text from an evaluation/notes field is an error message."""
    if not text:
        return False
    text_lower = text.lower().strip()
    return any(pattern in text_lower for pattern in _EVAL_ERROR_PATTERNS)


def _get_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def parse_webhook_payload(payload: dict) -> Optional[Dict]:
    """Extract article data from a Notion webhook payload.

    Args:
        payload: Raw webhook JSON payload from Notion

    Returns:
        Dict with normalized article fields, or None if parsing fails
    """
    try:
        # Notion webhook payloads vary; handle common structures
        data = payload.get("data", payload)

        # If it's a page object directly
        if "properties" in data:
            return _extract_properties(data)

        # If it wraps a page object
        if "page" in data:
            return _extract_properties(data["page"])

        # Try to extract page_id and fetch full data
        page_id = (
            data.get("page_id")
            or data.get("id")
            or payload.get("entity", {}).get("id")
        )
        if page_id:
            return fetch_page_data(page_id)

        logger.warning("Could not parse webhook payload structure")
        return None

    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}", exc_info=True)
        return None


def _extract_properties(page: dict) -> Dict:
    """Extract normalized fields from a Notion page properties object."""
    props = page.get("properties", {})
    page_id = page.get("id", "")

    def _get_title(prop_data):
        title_items = prop_data.get("title", [])
        return "".join(t.get("plain_text", "") for t in title_items)

    def _get_rich_text(prop_data):
        rt_items = prop_data.get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in rt_items)

    def _get_any_text(prop_data):
        """Extract text from any Notion property type that can hold text.
        Handles rich_text, title, formula (string), and rollup (array of text)."""
        p_type = prop_data.get("type", "")
        if p_type == "rich_text":
            return _get_rich_text(prop_data)
        if p_type == "title":
            return _get_title(prop_data)
        if p_type == "formula":
            formula = prop_data.get("formula", {}) or {}
            f_type = formula.get("type", "")
            if f_type == "string":
                return formula.get("string", "") or ""
            if f_type == "number":
                n = formula.get("number")
                return str(n) if n is not None else ""
        if p_type == "rollup":
            rollup = prop_data.get("rollup", {}) or {}
            if rollup.get("type") == "array":
                parts = []
                for item in rollup.get("array", []):
                    sub_type = item.get("type", "")
                    if sub_type == "rich_text":
                        parts.append("".join(t.get("plain_text", "") for t in item.get("rich_text", [])))
                    elif sub_type == "title":
                        parts.append("".join(t.get("plain_text", "") for t in item.get("title", [])))
                return " ".join(p for p in parts if p)
        return ""

    def _get_url(prop_data):
        return prop_data.get("url", "")

    def _get_number(prop_data):
        return prop_data.get("number", 0) or 0

    def _get_select(prop_data):
        sel = prop_data.get("select")
        return sel.get("name", "") if sel else ""

    def _get_multi_select(prop_data):
        items = prop_data.get("multi_select", [])
        return [item.get("name", "") for item in items]

    def _get_checkbox(prop_data):
        return prop_data.get("checkbox", False)

    def _get_date(prop_data):
        date_obj = prop_data.get("date")
        if date_obj and date_obj.get("start"):
            try:
                dt = datetime.fromisoformat(date_obj["start"])
                return dt.strftime("%d/%m/%Y")
            except Exception:
                return date_obj["start"]
        return ""

    # Build normalized data dict
    # Field name matching is flexible — tries common naming conventions
    result = {
        "page_id": page_id,
        "title": "",
        "summary": "",
        "relevant_info": "",
        "implications": "",
        "category": "",
        "publication_date": "",
        "source_url": "",
        "source_name": "",
        "credibility_score": 3.0,
        "relevancy_score": 3.0,
        "accuracy_score": 3.0,
        "overall_score": 3.0,
        "slide_generated": False,
    }

    # Diagnostic: log all Notion columns and their types so mismatches are visible
    logger.info(
        f"Notion page {page_id[:8]} columns: "
        + ", ".join(f"{n!r}({p.get('type', '?')})" for n, p in props.items())
    )

    for prop_name, prop_data in props.items():
        prop_type = prop_data.get("type", "")
        name_lower = prop_name.lower().strip()

        # Title / Name field
        if prop_type == "title" or name_lower in ("name", "title", "article title"):
            result["title"] = _get_title(prop_data)

        # Summary
        elif name_lower in ("summary", "article summary", "summary text"):
            result["summary"] = _get_rich_text(prop_data)

        # Relevant information
        elif "relevant" in name_lower or "additional" in name_lower:
            result["relevant_info"] = _get_rich_text(prop_data)

        # Implications — column is named "Implications" in current DB
        elif name_lower in ("implications", "client relevance", "business implications", "impact"):
            result["implications"] = _get_any_text(prop_data)
            logger.info(
                f"Matched implications column '{prop_name}' (type={prop_type}) → "
                f"{len(result['implications'])} chars"
            )

        # Client feedback fields — internal to scraper, not for slides
        elif name_lower in ("client rationale",):
            pass

        # Evaluation notes — skip; this contains source assessment text
        # (credibility/relevancy judgments) that shouldn't appear on the slide.
        # Stars are driven by the numeric score columns instead.
        elif "evaluation" in name_lower or "notes" in name_lower:
            pass

        # Category / Primary Theme / Themes
        elif name_lower in ("category", "primary theme", "theme", "themes", "type"):
            if prop_type == "select":
                result["category"] = _get_select(prop_data)
            elif prop_type == "multi_select":
                cats = _get_multi_select(prop_data)
                result["category"] = cats[0] if cats else ""

        # Publication date
        elif "date" in name_lower or "published" in name_lower:
            if prop_type == "date":
                result["publication_date"] = _get_date(prop_data)

        # Source URL / Article URL
        elif name_lower in ("article url", "source url", "url", "link"):
            result["source_url"] = _get_url(prop_data)

        # Source / Publication name
        elif name_lower in ("source", "publication", "source/publication"):
            if prop_type == "rich_text":
                result["source_name"] = _get_rich_text(prop_data)
            elif prop_type == "select":
                result["source_name"] = _get_select(prop_data)

        # Credibility score
        elif "credibility" in name_lower:
            score = float(_get_number(prop_data))
            if score > 0:
                result["credibility_score"] = score

        # Relevancy / Relevance score
        elif "relevan" in name_lower:
            score = float(_get_number(prop_data))
            if score > 0:
                result["relevancy_score"] = score

        # Accuracy score
        elif "accuracy" in name_lower:
            result["accuracy_score"] = float(_get_number(prop_data))

        # Overall score
        elif "overall" in name_lower:
            result["overall_score"] = float(_get_number(prop_data))

        # Slide Generated flag
        elif "slide" in name_lower and "generated" in name_lower:
            result["slide_generated"] = _get_checkbox(prop_data)

    return result


def fetch_page_data(page_id: str) -> Optional[Dict]:
    """Fetch full page data from Notion API."""
    try:
        url = f"{NOTION_API_URL}/pages/{page_id}"
        response = httpx.get(url, headers=_get_headers(), timeout=30)
        response.raise_for_status()
        page = response.json()
        return _extract_properties(page)
    except Exception as e:
        logger.error(f"Failed to fetch page {page_id}: {e}")
        return None


def query_unprocessed_articles() -> List[Dict]:
    """Query Notion database for articles that haven't been processed yet.

    Returns articles where 'Slide Generated' is unchecked/false.
    Handles pagination (Notion returns max 100 per page).
    """
    try:
        url = f"{NOTION_API_URL}/databases/{NOTION_DATABASE_ID}/query"

        filter_body = {
            "filter": {
                "or": [
                    {
                        "property": "Slide Generated",
                        "checkbox": {
                            "equals": False
                        }
                    }
                ]
            },
            "sorts": [
                {
                    "timestamp": "created_time",
                    "direction": "descending"
                }
            ]
        }

        results = []
        has_more = True

        while has_more:
            response = httpx.post(
                url,
                headers=_get_headers(),
                json=filter_body,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            for page in data.get("results", []):
                article = _extract_properties(page)
                if article and not article.get("slide_generated", False):
                    results.append(article)

            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")
            if has_more and next_cursor:
                filter_body["start_cursor"] = next_cursor
            else:
                has_more = False

        logger.info(f"Found {len(results)} unprocessed articles")
        return results

    except Exception as e:
        logger.error(f"Failed to query unprocessed articles: {e}")
        return []


def update_page_with_slide(page_id: str, slide_path: str) -> bool:
    """Update a Notion page: check the Slide Generated box.

    Tries to also set a Slide Link URL property if it exists in the DB.
    Falls back to just checking the box if Slide Link property doesn't exist.

    Args:
        page_id: Notion page ID
        slide_path: Local file path to the generated slide

    Returns:
        True if update succeeded
    """
    url = f"{NOTION_API_URL}/pages/{page_id}"
    file_url = f"file://{slide_path}"

    # First try: checkbox + slide link
    update_body = {
        "properties": {
            "Slide Generated": {
                "checkbox": True
            },
            "Slide Link": {
                "url": file_url
            }
        }
    }

    try:
        response = httpx.patch(
            url, headers=_get_headers(), json=update_body, timeout=30
        )
        response.raise_for_status()
        logger.info(f"Updated Notion page {page_id} with slide link")
        return True
    except Exception as e:
        logger.warning(f"Update with Slide Link failed ({e}), retrying checkbox only")

    # Fallback: just check the box (Slide Link property may not exist)
    update_body = {
        "properties": {
            "Slide Generated": {
                "checkbox": True
            }
        }
    }

    try:
        response = httpx.patch(
            url, headers=_get_headers(), json=update_body, timeout=30
        )
        response.raise_for_status()
        logger.info(f"Checked 'Slide Generated' for page {page_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Notion page {page_id}: {e}")
        return False


def update_page_comments(page_id: str, comments: str) -> bool:
    """Write validation comments to the Notion 'Comments' column.

    If the slide passed all checks, clears any previous comments.
    If issues were found, writes them as a rich-text block.

    Args:
        page_id: Notion page ID
        comments: Formatted comment string (empty = all clear)

    Returns:
        True if update succeeded
    """
    url = f"{NOTION_API_URL}/pages/{page_id}"

    # Build rich_text content — empty list clears the field
    if comments:
        rich_text_content = [{"type": "text", "text": {"content": comments}}]
    else:
        rich_text_content = [{"type": "text", "text": {"content": "All checks passed"}}]

    update_body = {
        "properties": {
            "Comments": {
                "rich_text": rich_text_content
            }
        }
    }

    try:
        response = httpx.patch(
            url, headers=_get_headers(), json=update_body, timeout=30
        )
        response.raise_for_status()
        if comments:
            logger.info(f"Wrote validation comments for page {page_id}")
        else:
            logger.info(f"Cleared comments (all checks passed) for page {page_id}")
        return True
    except Exception as e:
        # The Comments property might not exist yet — log but don't fail
        logger.warning(
            f"Could not update Comments for page {page_id}: {e}. "
            "Ensure a 'Comments' rich_text property exists in the Notion database."
        )
        return False


def mark_page_error(page_id: str, error_msg: str) -> bool:
    """Mark a page with an error status for manual review.

    Writes the error to the Comments column and leaves Slide Generated unchecked.
    """
    try:
        url = f"{NOTION_API_URL}/pages/{page_id}"

        # Try to write error to Comments column
        update_body = {
            "properties": {
                "Comments": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": f"Pipeline error: {error_msg[:1900]}"}
                    }]
                }
            }
        }
        response = httpx.patch(
            url, headers=_get_headers(), json=update_body, timeout=30
        )
        response.raise_for_status()
        logger.warning(f"Marked page {page_id} for review: {error_msg}")
        return True
    except Exception as e:
        logger.warning(f"Could not mark error for page {page_id}: {e}")
        return False
