"""
Selenium Capture Module - Captures article screenshot for slide generation.

Drop-in replacement for playwright_capture.py using Selenium + ChromeDriver.
Uses a desktop-width viewport for clean rendering without mobile-emulation
DPR scaling that caused skewed / weirdly-zoomed screenshots.

Takes one full-page screenshot after dismissing cookie banners and inline ads,
finds the headline position, then crops a single focused region covering the
headline, byline, hero image and opening paragraph.

Requirements:
    pip install selenium pillow
    Chrome browser installed (Selenium 4.6+ auto-manages ChromeDriver)
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional, Dict

from config import (
    BROWSER_HEADLESS, BROWSER_TIMEOUT,
    COOKIE_DISMISS_TIMEOUT, CACHE_DIR
)

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementNotInteractableException
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Viewport — desktop-width avoids mobile-emulation DPR scaling issues.
# 900px triggers single-column responsive layout on most news sites while
# keeping text readable and avoiding mobile zoom artifacts.
# ---------------------------------------------------------------------------
CAPTURE_WIDTH = 900
CAPTURE_HEIGHT = 900

# ---------------------------------------------------------------------------
# Cookie/popup dismissal selectors — ordered by specificity.
# Text-based matches are handled separately via XPath (see _dismiss_popups).
# ---------------------------------------------------------------------------
COOKIE_SELECTORS = [
    # CMP frameworks (OneTrust, Quantcast, etc.)
    '#onetrust-accept-btn-handler',
    '.onetrust-close-btn-handler',
    '#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll',
    '#CybotCookiebotDialogBodyButtonAccept',
    '[data-cmp-action="accept"]',
    '.qc-cmp2-summary-buttons button:first-child',
    '#didomi-notice-agree-button',
    '.fc-cta-consent',
    '.fc-button.fc-cta-consent',
    # Generic consent buttons
    'button[id*="cookie"][id*="accept"]',
    'button[class*="cookie"][class*="accept"]',
    'button[id*="consent"][id*="accept"]',
    '[class*="cookie-banner"] button[class*="accept"]',
    '[class*="cookie-consent"] button[class*="accept"]',
    '[class*="gdpr"] button[class*="accept"]',
    # Common close buttons on overlays
    '[class*="cookie"] [class*="close"]',
    '[class*="consent"] [class*="close"]',
    '[class*="banner"] [class*="close"]',
    '[aria-label*="cookie"] button',
    '[aria-label*="consent"] button',
]

# Text labels used for XPath-based button matching
COOKIE_BUTTON_TEXTS = [
    "Accept All", "Accept all", "Accept Cookies", "Accept cookies",
    "Accept", "I agree", "I Agree", "Agree", "OK", "Got it",
    "Allow", "Allow All", "Continue",
]

# ---------------------------------------------------------------------------
# JavaScript snippets.
# Selenium's execute_script() auto-wraps code in a function, so these use
# bare `return` statements — no arrow-function wrapper needed.
# ---------------------------------------------------------------------------

CLEANUP_JS = """
    let removed = 0;

    // 1. Remove cookie/consent overlays
    const overlaySelectors = [
        '[class*="cookie"]', '[class*="Cookie"]',
        '[class*="consent"]', '[class*="Consent"]',
        '[class*="gdpr"]', '[class*="GDPR"]',
        '[id*="cookie"]', '[id*="Cookie"]',
        '[id*="consent"]', '[id*="Consent"]',
        '[class*="cmp"]', '[id*="cmp"]',
        '.fc-consent-root',
        '#onetrust-banner-sdk',
        '#CybotCookiebotDialog',
        '#didomi-host',
        '[class*="qc-cmp"]',
    ];
    for (const sel of overlaySelectors) {
        document.querySelectorAll(sel).forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.position === 'fixed' || style.position === 'sticky' ||
                parseInt(style.zIndex) > 100 || el.tagName === 'DIALOG') {
                el.remove();
                removed++;
            }
        });
    }

    // 2. Make sticky/fixed headers static
    document.querySelectorAll('header, nav, [class*="sticky"], [class*="fixed"], [class*="toolbar"], [class*="ticker"]').forEach(el => {
        const style = window.getComputedStyle(el);
        if (style.position === 'fixed' || style.position === 'sticky') {
            el.style.position = 'relative';
            removed++;
        }
    });

    // 3. Remove ALL iframes (almost always ads)
    document.querySelectorAll('iframe').forEach(el => {
        el.remove();
        removed++;
    });

    // 4. Remove inline ads, promos, widgets, sidebars aggressively
    const adSelectors = [
        '[class*="ad-"]', '[class*="ad_"]', '[id*="ad-"]', '[id*="ad_"]',
        '[class*="advert"]', '[class*="sponsor"]',
        '[class*="promo"]',
        '[class*="widget"]', '[class*="sidebar"]',
        '[class*="related-articles"]', '[class*="recommended"]',
        '[data-ad]', '[data-advertisement]',
        '.azerion', '[class*="azerion"]',
        '[class*="result"]',
        '[class*="ticker"]',
        '[class*="score"]',
    ];
    for (const sel of adSelectors) {
        document.querySelectorAll(sel).forEach(el => {
            const tag = el.tagName.toLowerCase();
            if (tag === 'article' || tag === 'main') return;
            el.remove();
            removed++;
        });
    }

    // 5. Remove elements with "banner" in class (but not the main article banner/hero)
    document.querySelectorAll('[class*="banner"]').forEach(el => {
        const tag = el.tagName.toLowerCase();
        if (tag === 'article' || tag === 'main') return;
        if (el.querySelector('h1')) return;
        el.remove();
        removed++;
    });

    // 6. Remove non-article elements above h1
    const h1 = document.querySelector('article h1') || document.querySelector('h1');
    if (h1) {
        let current = h1;
        while (current && current.parentElement && current.parentElement !== document.documentElement) {
            let sibling = current.previousElementSibling;
            while (sibling) {
                const prev = sibling.previousElementSibling;
                const tag = sibling.tagName.toLowerCase();
                if (tag === 'script' || tag === 'style' || tag === 'link' || tag === 'meta') {
                    sibling = prev;
                    continue;
                }
                if (tag === 'header') {
                    sibling = prev;
                    continue;
                }
                sibling.remove();
                removed++;
                sibling = prev;
            }
            current = current.parentElement;
        }
    }

    // 7. Remove Google AdSense and common ad framework containers inside article
    const articleEl = document.querySelector('article') || document.querySelector('[class*="article"]') || document.querySelector('main');
    if (articleEl) {
        articleEl.querySelectorAll('ins.adsbygoogle, [data-ad-slot], [data-google-query-id], [class*="google-ad"], [id*="google_ads"], [class*="ad-container"], [class*="ad-wrapper"], [class*="advertisement"], div[id^="div-gpt-ad"]').forEach(el => {
            el.remove();
            removed++;
        });
        articleEl.querySelectorAll('div, aside').forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.position === 'absolute' || style.position === 'fixed') {
                el.remove();
                removed++;
            }
        });
    }

    // 8. Click any visible close/dismiss buttons on inline widgets
    document.querySelectorAll('[class*="close"], [aria-label*="close"], [aria-label*="dismiss"], button[class*="dismiss"]').forEach(btn => {
        try { btn.click(); removed++; } catch(e) {}
    });

    // 9. Restore body scroll
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.documentElement.style.overflow = '';

    return removed;
"""

FIND_HEADLINE_JS = """
    const selectors = [
        'article h1',
        '[class*="article-title"]',
        '[class*="headline"]',
        '[class*="post-title"]',
        'h1',
        '.entry-title',
    ];
    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el) {
            const rect = el.getBoundingClientRect();
            const y = rect.top + window.pageYOffset;
            return { y: y, height: rect.height, selector: sel };
        }
    }
    return null;
"""

PAGE_HEIGHT_JS = """
    return Math.max(
        document.body.scrollHeight,
        document.body.offsetHeight,
        document.documentElement.clientHeight,
        document.documentElement.scrollHeight,
        document.documentElement.offsetHeight
    );
"""


# ---------------------------------------------------------------------------
# Driver setup
# ---------------------------------------------------------------------------

def _build_driver() -> webdriver.Chrome:
    """Build a Chrome WebDriver with a desktop-width viewport.

    Uses --force-device-scale-factor=1 to guarantee 1:1 pixel mapping
    in screenshots (no DPR scaling).  Selenium 4.6+ auto-manages
    ChromeDriver via its built-in SeleniumManager.
    """
    options = Options()

    if BROWSER_HEADLESS:
        options.add_argument("--headless=new")

    options.add_argument(f"--window-size={CAPTURE_WIDTH},{CAPTURE_HEIGHT}")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(BROWSER_TIMEOUT / 1000)  # config is in ms
    return driver


# ---------------------------------------------------------------------------
# Full-page screenshot helper
# ---------------------------------------------------------------------------

def _take_fullpage_screenshot(driver: webdriver.Chrome, path: str) -> None:
    """Resize the window to the full document height, take screenshot, restore.

    Selenium doesn't natively support full-page screenshots, so we temporarily
    expand the viewport to fit the entire document.
    """
    original_size = driver.get_window_size()
    page_height = driver.execute_script(PAGE_HEIGHT_JS)

    # Cap height to avoid excessively large screenshots
    page_height = min(page_height, 15000)

    driver.set_window_size(CAPTURE_WIDTH, page_height)
    time.sleep(0.3)  # let layout reflow settle

    driver.save_screenshot(path)

    driver.set_window_size(original_size["width"], original_size["height"])


# ---------------------------------------------------------------------------
# Popup/cookie dismissal
# ---------------------------------------------------------------------------

def _dismiss_popups(driver: webdriver.Chrome) -> bool:
    """Try to dismiss common cookie banners and popups via button clicks."""
    dismissed = False

    # 1. CSS-selector-based matches
    # Use a short per-selector timeout (1s) — if a banner exists, its button
    # is visible almost immediately.  The full COOKIE_DISMISS_TIMEOUT is only
    # used for the overall attempt; per-selector we fail fast.
    per_selector_timeout = min(1.0, COOKIE_DISMISS_TIMEOUT / 1000)
    for selector in COOKIE_SELECTORS:
        try:
            btn = WebDriverWait(driver, per_selector_timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            btn.click()
            time.sleep(0.5)
            logger.info(f"Dismissed popup with selector: {selector}")
            dismissed = True
            break
        except (TimeoutException, NoSuchElementException,
                ElementNotInteractableException):
            continue

    if dismissed:
        return dismissed

    # 2. XPath text-based matches
    for text in COOKIE_BUTTON_TEXTS:
        xpath = (
            f"//button[normalize-space(.)='{text}'] | "
            f"//button[contains(normalize-space(.), '{text}')]"
        )
        try:
            btn = WebDriverWait(driver, 0.5).until(
                EC.element_to_be_clickable((By.XPATH, xpath))
            )
            if btn.is_displayed():
                btn.click()
                time.sleep(0.5)
                logger.info(f"Dismissed popup via text match: '{text}'")
                dismissed = True
                break
        except (TimeoutException, NoSuchElementException,
                ElementNotInteractableException):
            continue

    return dismissed


# ---------------------------------------------------------------------------
# Image cropping
# ---------------------------------------------------------------------------

def _crop_article_top(full_page_path: str, output_dir: Path,
                       headline_y: float) -> dict:
    """Crop the article's top section into a single focused image.

    Produces one clean screenshot covering the byline/publication logo,
    headline text, hero image, and the opening paragraph — exactly the
    content needed for the slide's left-side visual.

    Returns a dict keyed by template slot name.  Only 'main' is populated;
    the PPTX generator removes unused template shapes cleanly.
    """
    from PIL import Image

    results = {
        "byline": None,
        "headline": None,
        "main": None,
        "secondary": None,
        "footer": None,
    }

    try:
        img = Image.open(full_page_path)
        w, h = img.size

        # Start above the headline to include publication logo / byline area
        crop_top = max(0, int(headline_y) - 150)

        # Capture ~1400px from there — typically covers:
        #   - byline / publication logo (~100-150px)
        #   - headline text (~80-200px)
        #   - hero image (~400-600px)
        #   - first paragraph (~200-400px)
        crop_bottom = min(h, crop_top + 1400)

        if crop_bottom > crop_top + 50:
            cropped = img.crop((0, crop_top, w, crop_bottom))
            path = str(output_dir / "main.png")
            cropped.save(path)
            results["main"] = path
            logger.info(
                f"Cropped article top: y={crop_top}-{crop_bottom}px "
                f"({crop_bottom - crop_top}px tall, {w}px wide)"
            )

        img.close()

    except Exception as e:
        logger.error(f"Failed to crop article top: {e}", exc_info=True)

    return results


# ---------------------------------------------------------------------------
# Main capture (synchronous — Selenium is inherently sync)
# ---------------------------------------------------------------------------

def _capture_sync(article_url: str,
                  article_id: str = "default") -> Dict[str, Optional[str]]:
    """Full capture pipeline: navigate → dismiss popups → clean page →
    screenshot → crop article top.
    """
    output_dir = CACHE_DIR / article_id
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "byline": None,
        "headline": None,
        "main": None,
        "secondary": None,
        "footer": None,
    }

    driver = None
    try:
        driver = _build_driver()

        # Navigate
        logger.info(f"Navigating to: {article_url}")
        driver.get(article_url)
        time.sleep(2)  # wait for JS-rendered content

        # Dismiss cookie banners
        _dismiss_popups(driver)
        time.sleep(1)

        # Clean up overlays, sticky headers, inline ads, widgets
        removed = driver.execute_script(CLEANUP_JS)
        if removed and removed > 0:
            logger.info(f"Cleaned up {removed} overlay/ad/widget elements")
            time.sleep(1)
            # Second pass — some elements reappear after first removal
            removed2 = driver.execute_script(CLEANUP_JS)
            if removed2 and removed2 > 0:
                logger.info(f"Second cleanup pass removed {removed2} more elements")
                time.sleep(0.5)

        # Find the headline's document-relative Y position
        headline_info = driver.execute_script(FIND_HEADLINE_JS)
        headline_y = 0
        if headline_info:
            headline_y = headline_info["y"]
            logger.info(
                f"Found headline at y={headline_y}px "
                f"using {headline_info['selector']}"
            )
        else:
            logger.warning("Could not find headline — cropping from top")

        # Take full-page screenshot
        full_path = str(output_dir / "full_page.png")
        _take_fullpage_screenshot(driver, full_path)
        logger.info("Captured full-page screenshot")

        # Crop article top section
        results = _crop_article_top(full_path, output_dir, headline_y)

    except Exception as e:
        logger.error(
            f"Selenium capture failed for {article_url}: {e}", exc_info=True
        )

    finally:
        if driver:
            driver.quit()

    return results


# ---------------------------------------------------------------------------
# Public API — async + sync entry points
# ---------------------------------------------------------------------------

async def capture_article_images(article_url: str,
                                  article_id: str = "default") -> Dict[str, Optional[str]]:
    """Capture article screenshots — async wrapper around Selenium.

    Runs the synchronous Selenium driver in a background thread
    so it doesn't block the FastAPI event loop.
    """
    return await asyncio.to_thread(_capture_sync, article_url, article_id)


def capture_article_images_sync(article_url: str,
                                 article_id: str = "default") -> Dict[str, Optional[str]]:
    """Synchronous entry point for non-async callers."""
    return _capture_sync(article_url, article_id)
