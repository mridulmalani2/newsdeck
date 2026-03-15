"""
Utility functions for the automation system.
"""

import hashlib
import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import CACHE_DIR, MAX_RETRIES, RETRY_DELAY_SECONDS

logger = logging.getLogger(__name__)


def generate_article_id(url: str) -> str:
    """Generate a unique short ID from an article URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def format_date(date_str: str) -> str:
    """Normalize date string to DD/MM/YYYY format.

    Handles:
      - ISO format: 2025-04-20, 2025-04-20T00:00:00Z
      - Already formatted: 20/04/2025
      - Fallback: returns current date
    """
    if not date_str:
        return datetime.now().strftime("%d/%m/%Y")

    # Already in DD/MM/YYYY
    if len(date_str) == 10 and date_str[2] == "/" and date_str[5] == "/":
        return date_str

    # Try ISO format
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%fZ",
                "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
        try:
            dt = datetime.strptime(date_str.split("+")[0].split("Z")[0], fmt)
            return dt.strftime("%d/%m/%Y")
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_str}, using current date")
    return datetime.now().strftime("%d/%m/%Y")


def cleanup_cache(article_id: str):
    """Remove cached images for an article after slide generation."""
    cache_path = CACHE_DIR / article_id
    if cache_path.exists():
        shutil.rmtree(cache_path)
        logger.info(f"Cleaned up cache for: {article_id}")


def retry_with_backoff(func, *args, max_retries: int = None, **kwargs):
    """Execute a function with exponential backoff retry.

    Args:
        func: Function to execute
        max_retries: Override default max retries
        *args, **kwargs: Passed to func

    Returns:
        Function result or None on failure
    """
    retries = max_retries or MAX_RETRIES
    delay = RETRY_DELAY_SECONDS

    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(
                    f"Attempt {attempt + 1}/{retries} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(f"All {retries} attempts failed: {e}")
                raise


def sanitize_filename(text: str, max_length: int = 40) -> str:
    """Create a safe filename from text."""
    safe = "".join(c for c in text if c.isalnum() or c in " -_").strip()
    safe = safe.replace(" ", "_")
    return safe[:max_length]


def ensure_slide_output_dir(base_dir: Path) -> Path:
    """Ensure the slides output directory exists."""
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


def get_file_url(file_path: str) -> str:
    """Convert a local file path to a file:// URL."""
    abs_path = os.path.abspath(file_path)
    return f"file://{abs_path}"
