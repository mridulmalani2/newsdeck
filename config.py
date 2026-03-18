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

# === Grid System ===
# All layout positions derive from this grid.
# 1 inch = 914400 EMUs
# Slide dimensions: 13.33" × 7.5" (12192000 × 6858000 EMUs)


class Grid:
    """Grid system for consistent slide layout positioning.
    All values in EMUs. 1 inch = 914400 EMUs.
    """

    # Slide dimensions
    SLIDE_WIDTH = 12192000      # 13.33"
    SLIDE_HEIGHT = 6858000      # 7.5"

    # Margins
    MARGIN_LEFT = 731520        # 0.8"
    MARGIN_RIGHT = 731520       # 0.8"
    MARGIN_TOP = 548640         # 0.6"
    MARGIN_BOTTOM = 548640      # 0.6"
    GUTTER = 274320             # 0.3"

    # Derived edges
    RIGHT_EDGE = SLIDE_WIDTH - MARGIN_RIGHT             # 11460480
    CONTENT_WIDTH = SLIDE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT  # 10728960

    # Three-column layout
    IMAGE_COL_X = MARGIN_LEFT                           # 731520
    IMAGE_COL_W = 3840480                               # 4.2"
    LABEL_COL_X = IMAGE_COL_X + IMAGE_COL_W + GUTTER   # 4846320
    LABEL_COL_W = 1371600                               # 1.5"
    TEXT_COL_X = LABEL_COL_X + LABEL_COL_W + GUTTER    # 6492240
    TEXT_COL_W = RIGHT_EDGE - TEXT_COL_X                # 4968240 (~5.43")

    # Vertical zones
    CONTENT_Y = 1280160         # 1.4" — content sections start
    SECTION_H = 2168391         # 2.37" — height of each content section
    SECTION_SPACING = 164592    # 0.18" — gap between sections

    # Computed vertical positions
    IMPL_Y = CONTENT_Y + SECTION_H + SECTION_SPACING   # 3613143
    FOOTER_Y = IMPL_Y + SECTION_H + SECTION_SPACING    # 5946126
    FOOTER_H = 457200           # 0.5" — footer row height

    # Text padding (internal margins for text boxes)
    PADDING_X = 137160          # 0.15"
    PADDING_Y = 91440           # 0.10"



# === Template Layout Constants (grid-derived) ===

class TemplateLayout:
    """Element positions derived from the Grid system.
    All values in EMUs (English Metric Units).
    """

    # Slide dimensions
    SLIDE_WIDTH = Grid.SLIDE_WIDTH
    SLIDE_HEIGHT = Grid.SLIDE_HEIGHT

    # --- Element 11: Title (Titre 42) ---
    TITLE_X = 280657
    TITLE_Y = 627088
    TITLE_W = Grid.CONTENT_WIDTH
    TITLE_H = 350000
    TITLE_FONT_SIZE = 2000       # hundredths of pt (20pt)
    TITLE_MAX_CHARS = 90

    # --- Element 2: Category tag (Rectangle 5) ---
    CATEGORY_X = 390180
    CATEGORY_Y = 260059
    CATEGORY_W = 2012011
    CATEGORY_H = 295960
    CATEGORY_FONT_SIZE = 1200    # 12pt
    CATEGORY_MAX_CHARS = 25

    # --- Element 1: TGR Logo ---
    # Inherited from slide layout — no action needed

    # --- Article image (Picture 111) ---
    ARTICLE_IMG_X = 781696
    ARTICLE_IMG_Y = 1389079
    ARTICLE_IMG_W = Grid.IMAGE_COL_W
    ARTICLE_IMG_H = Grid.SECTION_H * 2 + Grid.SECTION_SPACING  # 4501374 — spans both sections

    # --- Element 3: Summary label (Rectangle 7) ---
    SUMMARY_LABEL_X = Grid.LABEL_COL_X
    SUMMARY_LABEL_Y = Grid.CONTENT_Y
    SUMMARY_LABEL_W = 1542904
    SUMMARY_LABEL_H = Grid.SECTION_H

    # --- Element 4: Implications label (Rectangle 8) ---
    IMPLICATIONS_LABEL_X = Grid.LABEL_COL_X
    IMPLICATIONS_LABEL_Y = Grid.IMPL_Y
    IMPLICATIONS_LABEL_W = 1542905
    IMPLICATIONS_LABEL_H = Grid.SECTION_H

    # --- Element 9: Summary + Relevant Info text box (Rectangle 13) ---
    SUMMARY_TEXT_X = 6628073
    SUMMARY_TEXT_Y = 1266363
    SUMMARY_TEXT_W = 5107887
    SUMMARY_TEXT_H = Grid.SECTION_H
    SUMMARY_FONT_SIZE = 1400     # 14pt default
    SUMMARY_FONT_MIN = 1000      # 10pt minimum fallback
    SUMMARY_MAX_WORDS = 120

    # --- Element 10: Implications text box (Rectangle 16) ---
    IMPLICATIONS_TEXT_X = 6628074
    IMPLICATIONS_TEXT_Y = 3601377
    IMPLICATIONS_TEXT_W = 5107886
    IMPLICATIONS_TEXT_H = Grid.SECTION_H
    IMPLICATIONS_FONT_SIZE = 1400
    IMPLICATIONS_FONT_MIN = 1000
    IMPLICATIONS_MAX_WORDS = 110

    # --- Source URL / Footer (ZoneTexte 4) ---
    SOURCE_X = Grid.MARGIN_LEFT
    SOURCE_Y = 6532298
    SOURCE_W = Grid.CONTENT_WIDTH
    SOURCE_H = 400110
    SOURCE_FONT_SIZE = 1000      # 10pt

    # --- Element 5: Credibility label (Rectangle 9) ---
    CREDIBILITY_LABEL_X = Grid.LABEL_COL_X
    CREDIBILITY_LABEL_Y = Grid.FOOTER_Y
    CREDIBILITY_LABEL_W = Grid.LABEL_COL_W
    CREDIBILITY_LABEL_H = Grid.FOOTER_H

    # --- Element 6: Credibility stars ---
    STAR_SIZE = 294198
    STAR_GAP = 91440            # 0.1" between stars
    CRED_STAR1_X = Grid.TEXT_COL_X
    CRED_STAR2_X = CRED_STAR1_X + STAR_SIZE + STAR_GAP             # 6877878
    CRED_STAR3_X = CRED_STAR2_X + STAR_SIZE + STAR_GAP             # 7263516
    CRED_STARS_Y = Grid.FOOTER_Y + (Grid.FOOTER_H - STAR_SIZE) // 2  # 6027627

    # --- Element 7: Relevance label (Rectangle 3, id=4) ---
    _AFTER_CRED_STARS = CRED_STAR3_X + STAR_SIZE + Grid.GUTTER     # 7832034
    RELEVANCE_LABEL_X = 7740594
    RELEVANCE_LABEL_Y = 5939971
    RELEVANCE_LABEL_W = Grid.LABEL_COL_W
    RELEVANCE_LABEL_H = Grid.FOOTER_H

    # --- Element 8: Relevance stars ---
    _REL_STAR_START = RELEVANCE_LABEL_X + RELEVANCE_LABEL_W + Grid.GUTTER // 2  # 9340794
    REL_STAR1_X = _REL_STAR_START
    REL_STAR2_X = _REL_STAR_START + STAR_SIZE + STAR_GAP           # 9726432
    REL_STAR3_X = _REL_STAR_START + 2 * (STAR_SIZE + STAR_GAP)    # 10112070
    REL_STARS_Y = CRED_STARS_Y                                      # same baseline

    # Star colors
    STAR_FILLED = "FFC000"   # Gold
    STAR_EMPTY = "FFFFFF"    # White

    # Image expansion bounding box
    _1CM = 360000
    IMG_BOX_LEFT = _1CM
    IMG_BOX_TOP = SUMMARY_TEXT_Y
    IMG_BOX_RIGHT = SUMMARY_LABEL_X - _1CM
    IMG_BOX_BOTTOM = CREDIBILITY_LABEL_Y + CREDIBILITY_LABEL_H


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
