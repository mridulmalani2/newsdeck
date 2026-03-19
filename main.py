"""
News Article Automation System - Main Server

FastAPI webhook server that:
1. Receives Notion webhook events for new articles
2. Captures article screenshots via Playwright
3. Generates PPTX slides matching the template
4. Updates Notion with slide links

Also supports:
- Manual processing via /process endpoint
- Batch processing of all unprocessed articles
- Health check endpoint
"""

import asyncio
import hashlib
import hmac
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import (
    WEBHOOK_PORT, WEBHOOK_SECRET, ENVIRONMENT,
    SLIDES_DIR, LOGS_DIR, NOTION_API_KEY, NOTION_DATABASE_ID
)
from modules.pptx_generator import generate_slide_from_notion_data, ArticleData, generate_slide, add_screenshot_slide
from modules.selenium_capture import capture_article_images
from modules.notion_client import (
    parse_webhook_payload, query_unprocessed_articles,
    update_page_with_slide, fetch_page_data, mark_page_error,
    update_page_comments
)
from modules.slide_validator import validate_article, format_comments
from modules.utils import (
    generate_article_id, format_date, cleanup_cache,
    retry_with_backoff, get_file_url
)

# === Logging Setup ===
LOG_FILE = LOGS_DIR / "automation.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("automation")

# === FastAPI App ===
app = FastAPI(
    title="News Article Slide Automation",
    description="Webhook-triggered slide generation from Notion articles",
    version="1.0.0",
)

# === Processing Stats ===
stats = {
    "total_processed": 0,
    "successful": 0,
    "failed": 0,
    "last_processed": None,
    "server_started": datetime.now().isoformat(),
}


# === Core Processing Pipeline ===

async def process_article(article_data: dict) -> Optional[str]:
    """Full pipeline: capture images → generate slide → update Notion.

    Args:
        article_data: Normalized article dict from Notion

    Returns:
        Path to generated slide, or None on failure
    """
    article_url = article_data.get("source_url", "")
    page_id = article_data.get("page_id", "")
    title = article_data.get("title", "Untitled")

    logger.info(f"{'='*60}")
    logger.info(f"Processing: {title[:60]}")
    logger.info(f"URL: {article_url}")
    logger.info(f"Page ID: {page_id}")

    try:
        # Step 1: Capture article images
        image_paths = {}
        if article_url:
            article_id = generate_article_id(article_url)
            logger.info(f"Step 1/4: Capturing screenshots (ID: {article_id})")
            image_paths = await capture_article_images(article_url, article_id)
            logger.info(f"Captured images: {[k for k, v in image_paths.items() if v]}")
        else:
            article_id = generate_article_id(title)
            logger.warning("No source URL — skipping screenshot capture")

        # Step 2: Normalize date format
        article_data["publication_date"] = format_date(
            article_data.get("publication_date", "")
        )

        # Step 3: Generate PPTX slide
        logger.info("Step 2/4: Generating slide")
        slide_path = generate_slide_from_notion_data(article_data, image_paths)

        if not slide_path:
            raise Exception("Slide generation returned None")

        logger.info(f"Step 3/4: Slide generated → {slide_path}")

        # Step 3b: Add backup screenshot slides (Slide 2: viewport, Slide 3: full-page)
        if article_url:
            logger.info("Adding backup screenshot slides (Slide 2: viewport, Slide 3: full-page)")
            await add_screenshot_slide(slide_path, article_url)

        # Step 4: Post-generation validation
        logger.info("Step 3/4: Validating generated slide")
        issues = validate_article(article_data, image_paths, slide_path)
        if issues:
            comments = format_comments(issues)
            logger.warning(f"Validation found {len(issues)} issue(s):")
            for issue in issues:
                logger.warning(f"  → {issue}")
        else:
            comments = ""
            logger.info("Validation passed — no issues found")

        # Step 5: Update Notion (checkbox + comments)
        if page_id and NOTION_API_KEY:
            logger.info("Step 4/4: Updating Notion")
            success = update_page_with_slide(page_id, slide_path)
            if success:
                logger.info("Notion updated successfully")
            else:
                logger.warning("Notion update failed — slide still saved locally")

            # Write validation comments to Notion
            update_page_comments(page_id, comments)
        else:
            logger.info("Step 4/4: Skipping Notion update (no page_id or API key)")

        # Cleanup cache
        cleanup_cache(article_id)

        # Update stats
        stats["total_processed"] += 1
        stats["successful"] += 1
        stats["last_processed"] = datetime.now().isoformat()

        logger.info(f"✓ Complete: {title[:60]}")
        logger.info(f"{'='*60}")
        return slide_path

    except Exception as e:
        stats["total_processed"] += 1
        stats["failed"] += 1
        logger.error(f"✗ Failed: {title[:60]} — {e}", exc_info=True)

        if page_id and NOTION_API_KEY:
            mark_page_error(page_id, str(e))

        return None


# === API Endpoints ===

@app.get("/")
async def root():
    """Server info."""
    return {
        "service": "News Article Slide Automation",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "status": "running",
        "stats": stats,
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    checks = {
        "server": "ok",
        "notion_configured": bool(NOTION_API_KEY and NOTION_DATABASE_ID),
        "template_exists": Path("templates/slide_template.pptx").exists(),
        "slides_dir_writable": os.access(str(SLIDES_DIR), os.W_OK),
        "logs_dir_writable": os.access(str(LOGS_DIR), os.W_OK),
    }
    all_ok = all(v in (True, "ok") for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
        "stats": stats,
    }


@app.post("/webhook/notion")
async def notion_webhook(request: Request, background_tasks: BackgroundTasks):
    """Receive Notion webhook events for new/updated articles.

    Validates webhook signature, extracts article data, and queues processing.
    """
    body = await request.body()

    # Validate webhook signature if secret is configured
    if WEBHOOK_SECRET:
        signature = request.headers.get("X-Notion-Signature", "")
        expected = hmac.new(
            WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, f"sha256={expected}"):
            logger.warning("Invalid webhook signature — rejected")
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()

    # Handle Notion webhook verification (URL verification challenge)
    if payload.get("type") == "url_verification":
        return {"challenge": payload.get("challenge", "")}

    logger.info(f"Webhook received: {payload.get('type', 'unknown')}")

    # Parse article data from payload
    article_data = parse_webhook_payload(payload)
    if not article_data:
        logger.warning("Could not parse article data from webhook")
        return {"status": "skipped", "reason": "Could not parse payload"}

    # Skip if already processed
    if article_data.get("slide_generated", False):
        logger.info(f"Skipping already-processed article: {article_data.get('title', '')[:50]}")
        return {"status": "skipped", "reason": "Already processed"}

    # Queue processing in background
    background_tasks.add_task(process_article, article_data)

    return {
        "status": "queued",
        "article": article_data.get("title", "")[:80],
    }


@app.post("/process")
async def manual_process(request: Request):
    """Manually trigger processing for a specific article.

    Body JSON:
    {
        "page_id": "notion-page-id",  // OR
        "url": "https://article-url.com",
        "title": "Article Title",
        "summary": "...",
        "implications": "...",
        "category": "REGULATIONS",
        "credibility_score": 3,
        "relevancy_score": 4,
        ...
    }
    """
    data = await request.json()

    # If page_id provided, fetch from Notion
    if "page_id" in data and NOTION_API_KEY:
        article_data = fetch_page_data(data["page_id"])
        if not article_data:
            raise HTTPException(status_code=404, detail="Page not found in Notion")
    else:
        # Use provided data directly
        article_data = {
            "page_id": data.get("page_id", ""),
            "title": data.get("title", "Untitled"),
            "summary": data.get("summary", ""),
            "relevant_info": data.get("relevant_info", ""),
            "implications": data.get("implications", ""),
            "category": data.get("category", "GENERAL INNOVATION"),
            "publication_date": data.get("publication_date", ""),
            "source_url": data.get("url", data.get("source_url", "")),
            "source_name": data.get("source_name", ""),
            "credibility_score": data.get("credibility_score", 3.0),
            "relevancy_score": data.get("relevancy_score", 3.0),
        }

    slide_path = await process_article(article_data)

    if slide_path:
        return {
            "status": "success",
            "slide_path": slide_path,
            "file_url": get_file_url(slide_path),
        }
    else:
        raise HTTPException(status_code=500, detail="Slide generation failed")


@app.post("/process/batch")
async def batch_process(background_tasks: BackgroundTasks):
    """Process all unprocessed articles from Notion database."""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        raise HTTPException(
            status_code=400,
            detail="Notion API key and database ID required for batch processing"
        )

    articles = query_unprocessed_articles()
    if not articles:
        return {"status": "complete", "message": "No unprocessed articles found"}

    # Queue all for background processing
    for article in articles:
        background_tasks.add_task(process_article, article)

    return {
        "status": "queued",
        "count": len(articles),
        "articles": [a.get("title", "")[:60] for a in articles],
    }


@app.post("/test")
async def test_slide():
    """Generate a test slide with sample data to verify the pipeline works."""
    logger.info("Generating test slide...")

    test_data = {
        "page_id": "",
        "title": "Test Article: Mercedes Criticizes 2026 Engine Regulations",
        "summary": "Mercedes has strongly opposed proposed changes to the 2026 F1 engine regulations, labeling them a \"joke.\"\nThe proposals aim to adjust the 50/50 power split between ICE and electric power during races.",
        "relevant_info": "While Mercedes opposes these changes, other teams like McLaren are open to discussions to ensure the success of the 2026 regulations.",
        "implications": "Mercedes' strong opposition to altering the 2026 engine regulations underscores potential instability in F1's technical direction.",
        "category": "REGULATIONS",
        "publication_date": "20/04/2025",
        "source_url": "https://www.the-race.com/formula-1/a-joke-mercedes-slams-f1-proposal-for-major-2026-engine-changes/",
        "source_name": "The Race",
        "credibility_score": 4.0,
        "relevancy_score": 4.5,
    }

    # Generate slide without images (text-only test)
    slide_path = generate_slide_from_notion_data(test_data, image_paths={})

    if slide_path:
        return {
            "status": "success",
            "slide_path": slide_path,
            "file_url": get_file_url(slide_path),
            "message": "Test slide generated (no images — text fields only)",
        }
    else:
        raise HTTPException(status_code=500, detail="Test slide generation failed")


@app.get("/stats")
async def get_stats():
    """Get processing statistics."""
    return stats


# === Batch Processing ===

async def run_batch():
    """Process all unprocessed articles from Notion (CLI mode)."""
    if not NOTION_API_KEY or not NOTION_DATABASE_ID:
        logger.error("Notion API key and database ID required for batch processing")
        logger.error("Set NOTION_API_KEY and NOTION_DATABASE_ID in .env")
        return

    logger.info("=" * 60)
    logger.info("Batch Processing — Finding unchecked articles...")
    logger.info("=" * 60)

    articles = query_unprocessed_articles()
    if not articles:
        logger.info("No unprocessed articles found. All done!")
        return

    logger.info(f"Found {len(articles)} articles to process")
    for i, article in enumerate(articles, 1):
        logger.info(f"\n[{i}/{len(articles)}] {article.get('title', 'Untitled')[:70]}")
        await process_article(article)

    logger.info("=" * 60)
    logger.info(f"Batch complete: {stats['successful']} succeeded, {stats['failed']} failed")
    logger.info("=" * 60)


# === Server Entry Point ===

def main():
    """Start the automation server, or run batch processing with --batch."""
    import argparse
    parser = argparse.ArgumentParser(description="News Article Slide Automation")
    parser.add_argument("--batch", action="store_true",
                        help="Process all unchecked articles and exit (no server)")
    args = parser.parse_args()

    if args.batch:
        asyncio.run(run_batch())
        return

    logger.info("=" * 60)
    logger.info("News Article Slide Automation Server")
    logger.info(f"Environment: {ENVIRONMENT}")
    logger.info(f"Port: {WEBHOOK_PORT}")
    logger.info(f"Slides output: {SLIDES_DIR}")
    logger.info(f"Logs: {LOG_FILE}")
    logger.info(f"Notion configured: {bool(NOTION_API_KEY)}")
    logger.info("=" * 60)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        reload=(ENVIRONMENT == "development"),
        log_level="info",
    )


if __name__ == "__main__":
    main()
