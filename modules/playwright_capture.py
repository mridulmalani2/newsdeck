"""
Playwright Capture Module - Captures article screenshots for slide left-side.

Uses a mobile viewport to get a clean, single-column article view.
Takes one full-page screenshot after dismissing cookie banners and inline ads,
then crops from the headline position into 5 regions matching the template.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Dict

from config import (
    BROWSER_HEADLESS, BROWSER_TIMEOUT,
    MOBILE_VIEWPORT_WIDTH, MOBILE_VIEWPORT_HEIGHT, MOBILE_USER_AGENT,
    COOKIE_DISMISS_TIMEOUT, CACHE_DIR
)

logger = logging.getLogger(__name__)

# Cookie/popup dismissal selectors — ordered by specificity
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
    'button[id*="cookie" i][id*="accept" i]',
    'button[class*="cookie" i][class*="accept" i]',
    'button[id*="consent" i][id*="accept" i]',
    '[class*="cookie-banner"] button[class*="accept" i]',
    '[class*="cookie-consent"] button[class*="accept" i]',
    '[class*="gdpr"] button[class*="accept" i]',
    # Text-based matches
    'button:has-text("Accept All")',
    'button:has-text("Accept all")',
    'button:has-text("Accept Cookies")',
    'button:has-text("Accept cookies")',
    'button:has-text("Accept")',
    'button:has-text("I agree")',
    'button:has-text("I Agree")',
    'button:has-text("Agree")',
    'button:has-text("OK")',
    'button:has-text("Got it")',
    'button:has-text("Allow")',
    'button:has-text("Allow All")',
    'button:has-text("Continue")',
    # Common close buttons on overlays
    '[class*="cookie"] [class*="close"]',
    '[class*="consent"] [class*="close"]',
    '[class*="banner"] [class*="close"]',
    '[aria-label*="cookie" i] button',
    '[aria-label*="consent" i] button',
]

# JS to clean up the page for a clean screenshot
CLEANUP_JS = """
() => {
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

    // 2. Make sticky/fixed headers static (keep them for logo, just de-sticky)
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
        '[class*="result"]',  // race results widgets
        '[class*="ticker"]',
        '[class*="score"]',
    ];
    for (const sel of adSelectors) {
        document.querySelectorAll(sel).forEach(el => {
            // Don't remove the main article itself
            const tag = el.tagName.toLowerCase();
            if (tag === 'article' || tag === 'main') return;
            // Remove if it's clearly not main content
            el.remove();
            removed++;
        });
    }

    // 5. Remove elements with "banner" in class (but not the main article banner/hero)
    document.querySelectorAll('[class*="banner"]').forEach(el => {
        const tag = el.tagName.toLowerCase();
        if (tag === 'article' || tag === 'main') return;
        // Keep if it contains the article headline h1
        if (el.querySelector('h1')) return;
        el.remove();
        removed++;
    });

    // 6. Remove non-article elements above h1 at every DOM level
    //    (race tickers, countdown widgets, promo bars, etc.)
    const h1 = document.querySelector('article h1') || document.querySelector('h1');
    if (h1) {
        // Walk from h1 up to body, at each level remove preceding siblings
        // that aren't ancestors of h1 and don't contain the site logo
        let current = h1;
        while (current && current.parentElement && current.parentElement !== document.documentElement) {
            let sibling = current.previousElementSibling;
            while (sibling) {
                const prev = sibling.previousElementSibling;
                const tag = sibling.tagName.toLowerCase();
                // Keep: scripts, styles, meta elements
                if (tag === 'script' || tag === 'style' || tag === 'link' || tag === 'meta') {
                    sibling = prev;
                    continue;
                }
                // Keep: header element (has publication logo)
                if (tag === 'header') {
                    sibling = prev;
                    continue;
                }
                // Remove everything else before the h1
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
        // Also remove small floating elements (likely ads) within article
        articleEl.querySelectorAll('div, aside').forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.position === 'absolute' || style.position === 'fixed') {
                el.remove();
                removed++;
            }
        });
    }

    // 8. Click any visible close/dismiss buttons on inline widgets
    document.querySelectorAll('[class*="close"], [aria-label*="close" i], [aria-label*="dismiss" i], button[class*="dismiss"]').forEach(btn => {
        try { btn.click(); removed++; } catch(e) {}
    });

    // 8. Restore body scroll
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.documentElement.style.overflow = '';

    return removed;
}
"""

# JS to find the headline's document-relative Y position
FIND_HEADLINE_JS = """
() => {
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
}
"""


async def capture_article_images(article_url: str,
                                  article_id: str = "default") -> Dict[str, Optional[str]]:
    """Capture screenshots from an article URL for slide generation.

    Uses a mobile viewport to get a clean single-column view.
    Takes one full-page screenshot, finds the headline position,
    then crops from there into 5 template regions.
    """
    from playwright.async_api import async_playwright

    output_dir = CACHE_DIR / article_id
    output_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "byline": None,
        "headline": None,
        "main": None,
        "secondary": None,
        "footer": None,
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=BROWSER_HEADLESS)
            context = await browser.new_context(
                viewport={
                    "width": MOBILE_VIEWPORT_WIDTH,
                    "height": MOBILE_VIEWPORT_HEIGHT,
                },
                user_agent=MOBILE_USER_AGENT,
                is_mobile=True,
                has_touch=True,
            )
            page = await context.new_page()

            # Navigate to article
            logger.info(f"Navigating to: {article_url} (mobile viewport)")
            await page.goto(article_url, wait_until="networkidle",
                          timeout=BROWSER_TIMEOUT)

            # Wait for content to load
            await page.wait_for_timeout(2000)

            # Dismiss cookie banners — try button clicks first
            await _dismiss_popups(page)
            await page.wait_for_timeout(1000)

            # Clean up: remove overlays, sticky headers, inline ads, widgets
            removed = await page.evaluate(CLEANUP_JS)
            if removed > 0:
                logger.info(f"Cleaned up {removed} overlay/ad/widget elements")
                await page.wait_for_timeout(1000)
                # Second pass — some elements reappear after first removal
                removed2 = await page.evaluate(CLEANUP_JS)
                if removed2 > 0:
                    logger.info(f"Second cleanup pass removed {removed2} more elements")
                    await page.wait_for_timeout(500)

            # Find the headline's document-relative Y position
            headline_info = await page.evaluate(FIND_HEADLINE_JS)
            headline_y = 0
            if headline_info:
                headline_y = headline_info['y']
                logger.info(f"Found headline at y={headline_y}px using {headline_info['selector']}")
            else:
                logger.warning("Could not find headline — cropping from top")

            # Take full-page screenshot
            full_path = str(output_dir / "full_page.png")
            await page.screenshot(path=full_path, full_page=True)
            logger.info("Captured full mobile page screenshot")

            # Crop from headline position into 5 template regions
            results = _crop_from_headline(full_path, output_dir, headline_y)

            await browser.close()

    except Exception as e:
        logger.error(f"Playwright capture failed for {article_url}: {e}", exc_info=True)
        results = _generate_placeholders(results, output_dir)

    return results


async def _dismiss_popups(page):
    """Try to dismiss common cookie banners and popups via button clicks."""
    dismissed = False
    for selector in COOKIE_SELECTORS:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=800):
                await btn.click(timeout=2000)
                await page.wait_for_timeout(500)
                logger.info(f"Dismissed popup with selector: {selector}")
                dismissed = True
                break
        except Exception:
            continue

    if not dismissed:
        # Broader approach: role-based button matching
        try:
            for text in ["Accept", "Agree", "Allow", "OK", "Got it", "Continue"]:
                btn = page.get_by_role("button", name=text, exact=False).first
                if await btn.is_visible(timeout=500):
                    await btn.click(timeout=2000)
                    await page.wait_for_timeout(500)
                    logger.info(f"Dismissed popup via role button: '{text}'")
                    dismissed = True
                    break
        except Exception:
            pass

    return dismissed


def _crop_from_headline(full_page_path: str, output_dir: Path,
                         headline_y: float) -> dict:
    """Crop a full-page mobile screenshot into 5 template regions.

    Starts cropping from slightly above the headline position to include
    the publication logo, then divides the article content into 5 sections
    matching the template's image slot proportions.

    Template image slots (vertical proportions of left column):
      byline:    ~6%  — publication logo above headline
      headline:  ~10% — headline text
      main:      ~32% — hero image + initial content
      secondary: ~32% — article body continuation
      footer:    ~12% — bottom section
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

        # Start cropping from above the headline to include the publication logo
        # Go back ~200px above the headline for the byline area (logos, pub name)
        crop_start = max(0, int(headline_y) - 200)

        # Total content height to capture (~2400px covers a good article length)
        # This maps to the template's left column which is ~5.6 inches tall
        total_capture = min(2400, h - crop_start)

        # Define regions as pixel offsets from crop_start
        # Proportions match template slot heights
        regions = {
            "byline":    (0, int(total_capture * 0.06)),
            "headline":  (int(total_capture * 0.06), int(total_capture * 0.16)),
            "main":      (int(total_capture * 0.16), int(total_capture * 0.48)),
            "secondary": (int(total_capture * 0.48), int(total_capture * 0.80)),
            "footer":    (int(total_capture * 0.80), int(total_capture * 0.95)),
        }

        for key, (top_offset, bottom_offset) in regions.items():
            top_px = crop_start + top_offset
            bottom_px = crop_start + bottom_offset

            # Clamp to image bounds
            top_px = min(top_px, h - 1)
            bottom_px = min(bottom_px, h)

            if bottom_px <= top_px:
                continue

            cropped = img.crop((0, top_px, w, bottom_px))
            path = str(output_dir / f"{key}.png")
            cropped.save(path)
            results[key] = path
            logger.info(f"Cropped {key}: y={top_px}-{bottom_px}px ({bottom_px - top_px}px tall)")

        img.close()

    except Exception as e:
        logger.error(f"Failed to crop regions: {e}", exc_info=True)
        results = _generate_placeholders(results, output_dir)

    return results


def _generate_placeholders(results: dict, output_dir: Path) -> dict:
    """Generate solid-color placeholder images when capture completely fails."""
    try:
        from PIL import Image, ImageDraw

        output_dir.mkdir(parents=True, exist_ok=True)

        sizes = {
            "byline": (400, 80),
            "headline": (600, 120),
            "main": (600, 400),
            "secondary": (600, 400),
            "footer": (600, 120),
        }

        for key, (w, h) in sizes.items():
            if results[key] is None:
                path = str(output_dir / f"{key}_placeholder.png")
                img = Image.new("RGB", (w, h), color=(240, 240, 240))
                draw = ImageDraw.Draw(img)
                text = f"[{key.upper()}]"
                draw.text((w // 2 - 40, h // 2 - 10), text, fill=(180, 180, 180))
                img.save(path)
                results[key] = path

    except Exception as e:
        logger.warning(f"Placeholder generation failed: {e}")

    return results


def capture_article_images_sync(article_url: str,
                                 article_id: str = "default") -> Dict[str, Optional[str]]:
    """Synchronous wrapper for capture_article_images."""
    return asyncio.run(capture_article_images(article_url, article_id))
