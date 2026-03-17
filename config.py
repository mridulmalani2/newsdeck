"""
Configuration & environment variables for the News Article Automation System.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === Base Paths ===
BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
SLIDES_DIR = Path(os.getenv("SLIDES_OUTPUT_DIR", str(BASE_DIR / "slides")))
LOGS_DIR = Path(os.getenv("LOGS_DIR", str(BASE_DIR / "logs")))
CACHE_DIR = BASE_DIR / "cache"
TEMPLATE_PATH = TEMPLATES_DIR / "slide_template.pptx"

# Ensure directories exist
SLIDES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# === Notion Configuration ===
NOTION_API_KEY = os.getenv("NOTION_API_KEY", "")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# === Server Configuration ===
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# === Playwright Configuration ===
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "true").lower() == "true"
BROWSER_TIMEOUT = int(os.getenv("BROWSER_TIMEOUT", "30000"))
VIEWPORT_WIDTH = int(os.getenv("VIEWPORT_WIDTH", "1280"))
VIEWPORT_HEIGHT = int(os.getenv("VIEWPORT_HEIGHT", "720"))

# Mobile viewport for clean article screenshots (iPhone 14 dimensions)
MOBILE_VIEWPORT_WIDTH = int(os.getenv("MOBILE_VIEWPORT_WIDTH", "390"))
MOBILE_VIEWPORT_HEIGHT = int(os.getenv("MOBILE_VIEWPORT_HEIGHT", "844"))
MOBILE_USER_AGENT = os.getenv(
    "MOBILE_USER_AGENT",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
COOKIE_DISMISS_TIMEOUT = int(os.getenv("COOKIE_DISMISS_TIMEOUT", "5000"))

# === Article Processing ===
IMAGE_EXTRACTION_TIMEOUT = int(os.getenv("IMAGE_EXTRACTION_TIMEOUT", "15"))
MAX_IMAGES_TO_CAPTURE = int(os.getenv("MAX_IMAGES_TO_CAPTURE", "4"))
MIN_IMAGE_SIZE_KB = int(os.getenv("MIN_IMAGE_SIZE_KB", "50"))

# === Error Handling ===
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "5"))

# === Template Layout Constants (EMUs - English Metric Units) ===
# 1 inch = 914400 EMUs
# Slide dimensions: 13.33" × 7.5" (12192000 × 6858000 EMUs)

class TemplateLayout:
    """Exact positions from the .potx template (slide_template.pptx).
    All values in EMUs (English Metric Units). 1 inch = 914400 EMUs.
    Slide dimensions: 13.33" x 7.5" (12192000 x 6858000 EMUs).
    """

    # Slide dimensions
    SLIDE_WIDTH = 12192000
    SLIDE_HEIGHT = 6858000

    # --- Element 11: Title (Titre 42) ---
    # Bold 20pt, normAutofit, vertically centered
    TITLE_X = 125413
    TITLE_Y = 394620
    TITLE_W = 11000856
    TITLE_H = 406168
    TITLE_FONT_SIZE = 2000       # hundredths of pt (20pt)
    TITLE_MAX_CHARS = 90         # fits ~90 chars at 20pt bold

    # --- Element 2: Category tag (Rectangle 5) ---
    # 12pt centered text, red border
    CATEGORY_X = 156190
    CATEGORY_Y = 87943
    CATEGORY_W = 2012011
    CATEGORY_H = 295960
    CATEGORY_FONT_SIZE = 1200    # 12pt
    CATEGORY_MAX_CHARS = 25      # e.g. "GENERAL INNOVATION" = 18 chars

    # --- Element 12: Date (ZoneTexte 6) ---
    # 11pt, auto-size to content, below category on the left
    DATE_X = 156190
    DATE_Y = 802333
    DATE_W = 928459
    DATE_H = 261610
    DATE_FONT_SIZE = 1100        # 11pt

    # --- Element 1: TGR Logo ---
    # Inherited from slide layout (Layout19, Picture 2)
    # pos=(11182076, 194549) size=(872930, 263759)
    # No action needed — layout provides it automatically

    # --- Article image (Picture 15) ---
    # Single large image on the left side
    ARTICLE_IMG_X = 250951
    ARTICLE_IMG_Y = 1749107
    ARTICLE_IMG_W = 4283778
    ARTICLE_IMG_H = 4068762

    # --- Element 3: Summary label (Rectangle 7) ---
    SUMMARY_LABEL_X = 4837083
    SUMMARY_LABEL_Y = 1260608
    SUMMARY_LABEL_W = 1567207
    SUMMARY_LABEL_H = 2168391

    # --- Element 4: Implications label (Rectangle 8) ---
    IMPLICATIONS_LABEL_X = 4837083
    IMPLICATIONS_LABEL_Y = 3550098
    IMPLICATIONS_LABEL_W = 1567207
    IMPLICATIONS_LABEL_H = 2168391

    # --- Element 9: Summary + Relevant Info text box (Rectangle 13) ---
    SUMMARY_TEXT_X = 6432218
    SUMMARY_TEXT_Y = 1260608
    SUMMARY_TEXT_W = 5319681
    SUMMARY_TEXT_H = 2168391
    SUMMARY_FONT_SIZE = 1400     # 14pt default
    SUMMARY_FONT_MIN = 1000      # 10pt minimum fallback
    SUMMARY_MAX_WORDS = 120      # recommended max for clean fit at 14pt

    # --- Element 10: Implications text box (Rectangle 16) ---
    IMPLICATIONS_TEXT_X = 6432217
    IMPLICATIONS_TEXT_Y = 3561349
    IMPLICATIONS_TEXT_W = 5319681
    IMPLICATIONS_TEXT_H = 2168391
    IMPLICATIONS_FONT_SIZE = 1400
    IMPLICATIONS_FONT_MIN = 1000
    IMPLICATIONS_MAX_WORDS = 110

    # --- Source URL (ZoneTexte 4) ---
    SOURCE_X = 6146
    SOURCE_Y = 6618656
    SOURCE_W = 8131896
    SOURCE_H = 246221
    SOURCE_FONT_SIZE = 1000      # 10pt

    # --- Element 5: Credibility label (Rectangle 9) ---
    CREDIBILITY_LABEL_X = 4837083
    CREDIBILITY_LABEL_Y = 5839588
    CREDIBILITY_LABEL_W = 1567207
    CREDIBILITY_LABEL_H = 646718

    # --- Element 6: Credibility stars ---
    CRED_STAR1_X = 6838122
    CRED_STAR2_X = 7222576
    CRED_STAR3_X = 7607030
    CRED_STARS_Y = 5987332
    STAR_SIZE = 294198

    # --- Element 7: Relevance label (Rectangle 1) ---
    RELEVANCE_LABEL_X = 8395841
    RELEVANCE_LABEL_Y = 5839588
    RELEVANCE_LABEL_W = 1567207
    RELEVANCE_LABEL_H = 646718

    # --- Element 8: Relevance stars ---
    REL_STAR1_X = 10408256
    REL_STAR2_X = 10792710
    REL_STAR3_X = 11177164
    REL_STARS_Y = 5987332

    # Star colors
    STAR_FILLED = "FFC000"   # Gold
    STAR_EMPTY = "FFFFFF"    # White


# === Category-to-color mapping ===
CATEGORY_COLORS = {
    "REGULATIONS": "FF0000",
    "M&A": "FF0000",
    "COMPETITIVE MOVE": "FF0000",
    "PERFORMANCE": "FF0000",
    "GENERAL INNOVATION": "FF0000",
    "TESTING & SIMULATION": "FF0000",
    "COOLING SYSTEMS": "FF0000",
    "AERODYNAMICS": "FF0000",
    "REGULATIONS & COMPLIANCE": "FF0000",
}

# Default color for unknown categories
DEFAULT_CATEGORY_COLOR = "FF0000"
