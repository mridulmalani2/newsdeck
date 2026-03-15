"""
Playwright Capture Module - Captures article screenshots for slide left-side.

Extracts:
1. Publication logo / byline area (top of article)
2. Headline text area
3. Main hero/featured image
4. Secondary inline image
5. Footer / bottom section

Uses smart fallbacks if elements aren't found.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, Dict

from config import (
    BROWSER_HEADLESS, BROWSER_TIMEOUT, VIEWPORT_WIDTH, VIEWPORT_HEIGHT,
    IMAGE_EXTRACTION_TIMEOUT, CACHE_DIR
)

logger = logging.getLogger(__name__)


async def capture_article_images(article_url: str,
                                  article_id: str = "default") -> Dict[str, Optional[str]]:
    """Capture screenshots from an article URL for slide generation.

    Args:
        article_url: Full URL of the article
        article_id: Unique identifier for cache folder naming

    Returns:
        Dict with keys: byline, headline, main, secondary, footer
        Values are file paths or None if capture failed
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
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            # Navigate to article
            logger.info(f"Navigating to: {article_url}")
            await page.goto(article_url, wait_until="networkidle",
                          timeout=BROWSER_TIMEOUT)

            # Wait for content to load
            await page.wait_for_timeout(2000)

            # Close cookie banners / popups
            await _dismiss_popups(page)

            # === Capture 1: Full page screenshot for fallback ===
            full_path = str(output_dir / "full_page.png")
            await page.screenshot(path=full_path, full_page=True)
            logger.info("Captured full page screenshot")

            # === Capture 2: Byline area (publication name + author) ===
            byline_path = await _capture_byline(page, output_dir)
            if byline_path:
                results["byline"] = byline_path

            # === Capture 3: Headline area ===
            headline_path = await _capture_headline(page, output_dir)
            if headline_path:
                results["headline"] = headline_path

            # === Capture 4: Hero/main image ===
            main_path = await _capture_hero_image(page, output_dir)
            if main_path:
                results["main"] = main_path

            # === Capture 5: Secondary inline image ===
            secondary_path = await _capture_secondary_image(page, output_dir)
            if secondary_path:
                results["secondary"] = secondary_path

            # === Capture 6: Footer / article continuation ===
            footer_path = await _capture_footer(page, output_dir)
            if footer_path:
                results["footer"] = footer_path

            # === Fallback: use viewport crops of full page ===
            results = _apply_fallbacks(results, full_path, output_dir)

            await browser.close()

    except Exception as e:
        logger.error(f"Playwright capture failed for {article_url}: {e}", exc_info=True)
        # Generate placeholder images
        results = _generate_placeholders(results, output_dir)

    return results


async def _dismiss_popups(page):
    """Try to dismiss common cookie banners and popups."""
    selectors = [
        'button[id*="cookie" i]',
        'button[class*="cookie" i]',
        'button[id*="accept" i]',
        'button[class*="accept" i]',
        'button[id*="consent" i]',
        '[class*="cookie-banner"] button',
        '[class*="gdpr"] button',
        'button:has-text("Accept")',
        'button:has-text("Accept All")',
        'button:has-text("I agree")',
        'button:has-text("OK")',
        'button:has-text("Got it")',
    ]
    for selector in selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=1000):
                await btn.click()
                await page.wait_for_timeout(500)
                logger.info(f"Dismissed popup with selector: {selector}")
                return
        except Exception:
            continue


async def _capture_byline(page, output_dir: Path) -> Optional[str]:
    """Capture the publication name / byline area."""
    selectors = [
        'header .logo',
        '[class*="site-logo"]',
        '[class*="publication"]',
        '[class*="masthead"]',
        'header img[src*="logo"]',
        '.author-info',
        '[class*="byline"]',
        'header',
    ]
    for selector in selectors:
        try:
            elem = page.locator(selector).first
            if await elem.is_visible(timeout=2000):
                path = str(output_dir / "byline.png")
                await elem.screenshot(path=path)
                # Check file size
                if os.path.getsize(path) > 1000:
                    logger.info(f"Captured byline with: {selector}")
                    return path
        except Exception:
            continue
    return None


async def _capture_headline(page, output_dir: Path) -> Optional[str]:
    """Capture the article headline area."""
    selectors = [
        'article h1',
        '[class*="article-title"]',
        '[class*="headline"]',
        '[class*="post-title"]',
        'h1',
        '.entry-title',
    ]
    for selector in selectors:
        try:
            elem = page.locator(selector).first
            if await elem.is_visible(timeout=2000):
                # Get bounding box and expand to include surrounding context
                box = await elem.bounding_box()
                if box:
                    # Capture a wider area around the headline
                    path = str(output_dir / "headline.png")
                    await page.screenshot(
                        path=path,
                        clip={
                            "x": max(0, box["x"] - 20),
                            "y": max(0, box["y"] - 10),
                            "width": min(VIEWPORT_WIDTH, box["width"] + 40),
                            "height": box["height"] + 40
                        }
                    )
                    logger.info(f"Captured headline with: {selector}")
                    return path
        except Exception:
            continue
    return None


async def _capture_hero_image(page, output_dir: Path) -> Optional[str]:
    """Capture the main hero/featured image."""
    selectors = [
        'article img[class*="featured"]',
        '[class*="hero-image"] img',
        '[class*="featured-image"] img',
        'article figure img',
        'article img',
        '.post-thumbnail img',
        'img[class*="wp-post-image"]',
    ]
    for selector in selectors:
        try:
            elem = page.locator(selector).first
            if await elem.is_visible(timeout=2000):
                box = await elem.bounding_box()
                if box and box["width"] > 200 and box["height"] > 100:
                    path = str(output_dir / "main.png")
                    await elem.screenshot(path=path)
                    if os.path.getsize(path) > 5000:
                        logger.info(f"Captured hero image with: {selector}")
                        return path
        except Exception:
            continue
    return None


async def _capture_secondary_image(page, output_dir: Path) -> Optional[str]:
    """Capture a secondary inline image from the article body."""
    try:
        images = page.locator('article img, .post-content img, .entry-content img')
        count = await images.count()
        # Skip the first image (hero), grab second or third
        for i in range(1, min(count, 4)):
            try:
                img = images.nth(i)
                if await img.is_visible(timeout=1000):
                    box = await img.bounding_box()
                    if box and box["width"] > 150 and box["height"] > 80:
                        path = str(output_dir / "secondary.png")
                        await img.screenshot(path=path)
                        if os.path.getsize(path) > 3000:
                            logger.info(f"Captured secondary image (index {i})")
                            return path
            except Exception:
                continue
    except Exception:
        pass
    return None


async def _capture_footer(page, output_dir: Path) -> Optional[str]:
    """Capture a section of the article body for the footer area."""
    try:
        # Scroll down and capture a mid-article section
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.3)")
        await page.wait_for_timeout(500)

        path = str(output_dir / "footer.png")
        # Capture viewport at this scroll position
        await page.screenshot(
            path=path,
            clip={
                "x": 0,
                "y": 0,
                "width": VIEWPORT_WIDTH,
                "height": 200
            }
        )
        logger.info("Captured footer section")
        return path
    except Exception:
        return None


def _apply_fallbacks(results: dict, full_page_path: str,
                      output_dir: Path) -> dict:
    """Apply fallback crops from full-page screenshot for any missing images."""
    try:
        from PIL import Image

        if not os.path.exists(full_page_path):
            return results

        img = Image.open(full_page_path)
        w, h = img.size

        # Fallback crops (relative positions)
        fallback_crops = {
            "byline": (0, 0, min(w, 500), min(h, 100)),
            "headline": (0, 0, w, min(h, 180)),
            "main": (0, min(h, 200), w, min(h, 700)),
            "secondary": (0, min(h, 700), w, min(h, 1200)),
            "footer": (0, min(h, 1200), w, min(h, 1500)),
        }

        for key, crop_box in fallback_crops.items():
            if results[key] is None:
                path = str(output_dir / f"{key}_fallback.png")
                cropped = img.crop(crop_box)
                cropped.save(path)
                results[key] = path
                logger.info(f"Applied fallback crop for: {key}")

        img.close()

    except Exception as e:
        logger.warning(f"Fallback crop failed: {e}")

    return results


def _generate_placeholders(results: dict, output_dir: Path) -> dict:
    """Generate solid-color placeholder images when capture completely fails."""
    try:
        from PIL import Image, ImageDraw, ImageFont

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
