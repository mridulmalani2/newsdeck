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
TEMPLATE_PATH = TEMPLATES_DIR / "Project_F_Update_20250429-FinalVersion.pptx"

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
    """Exact positions from the analyzed template XML."""

    # Slide dimensions
    SLIDE_WIDTH = 12192000
    SLIDE_HEIGHT = 6858000

    # Title bar
    TITLE_X = 125413
    TITLE_Y = 394620
    TITLE_W = 11000856
    TITLE_H = 406168

    # Category tag (top-left red-bordered box)
    CATEGORY_X = 156190
    CATEGORY_Y = 87943
    CATEGORY_W = 2012011
    CATEGORY_H = 295960

    # Date text box
    DATE_X = 3549488
    DATE_Y = 1266686
    DATE_W = 928459
    DATE_H = 261610

    # Left-side images
    # Publication logo/byline area
    BYLINE_IMG_X = 529637
    BYLINE_IMG_Y = 938735
    BYLINE_IMG_W = 1567207
    BYLINE_IMG_H = 326501

    # Article headline screenshot
    HEADLINE_IMG_X = 380598
    HEADLINE_IMG_Y = 1521378
    HEADLINE_IMG_W = 4246389
    HEADLINE_IMG_H = 533977

    # Main article image (top)
    MAIN_IMG_X = 529638
    MAIN_IMG_Y = 2151136
    MAIN_IMG_W = 3948310
    MAIN_IMG_H = 1656170

    # Secondary article image (bottom)
    SEC_IMG_X = 532249
    SEC_IMG_Y = 3807306
    SEC_IMG_W = 3943014
    SEC_IMG_H = 1632397

    # Footer article screenshot
    FOOTER_IMG_X = 526953
    FOOTER_IMG_Y = 5439703
    FOOTER_IMG_W = 3948310
    FOOTER_IMG_H = 615854

    # Center column label boxes (red-bordered)
    SUMMARY_LABEL_X = 5041127
    SUMMARY_LABEL_Y = 1260608
    SUMMARY_LABEL_W = 1363163
    SUMMARY_LABEL_H = 2168391

    IMPLICATIONS_LABEL_X = 5041127
    IMPLICATIONS_LABEL_Y = 3550098
    IMPLICATIONS_LABEL_W = 1363163
    IMPLICATIONS_LABEL_H = 2168391

    # Right-side content boxes
    SUMMARY_TEXT_X = 6432218
    SUMMARY_TEXT_Y = 1260608
    SUMMARY_TEXT_W = 5319681
    SUMMARY_TEXT_H = 2168391

    IMPLICATIONS_TEXT_X = 6432217
    IMPLICATIONS_TEXT_Y = 3561349
    IMPLICATIONS_TEXT_W = 5319681
    IMPLICATIONS_TEXT_H = 2168391

    # Source URL text box
    SOURCE_X = 6146
    SOURCE_Y = 6618656
    SOURCE_W = 8131896
    SOURCE_H = 246221

    # Credibility section
    CREDIBILITY_LABEL_X = 5041127
    CREDIBILITY_LABEL_Y = 5839588
    CREDIBILITY_LABEL_W = 1363163
    CREDIBILITY_LABEL_H = 646718

    # Credibility stars (3 stars, spaced ~384454 EMUs apart)
    CRED_STAR1_X = 6838122
    CRED_STAR2_X = 7222576
    CRED_STAR3_X = 7607030
    CRED_STARS_Y = 5987332
    STAR_SIZE = 294198

    # Relevancy section
    RELEVANCY_LABEL_X = 8674871
    RELEVANCY_LABEL_Y = 5839588
    RELEVANCY_LABEL_W = 1363163
    RELEVANCY_LABEL_H = 646718

    # Relevancy stars
    REL_STAR1_X = 10408256
    REL_STAR2_X = 10792710
    REL_STAR3_X = 11177164
    REL_STARS_Y = 5987332

    # Star colors (EMU hex)
    STAR_FILLED = "FFC000"   # Gold
    STAR_EMPTY = "FFFFFF"    # White (bg1)


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
