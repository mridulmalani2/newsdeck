# News Article Slide Automation System

Fully automated pipeline that processes F1/motorsport news articles from a Notion database, captures article screenshots, generates professionally designed PPTX slides matching the Project F template, validates output quality, and updates Notion with results — all without human oversight or AI intervention.

## Architecture

```
Notion DB (new row)
   ↓ webhook / batch trigger
FastAPI Server (main.py)
   ↓
1. Selenium Capture → screenshot of article page
   - Cloudflare challenge detection + auto-wait
   - Cookie banner / GDPR popup auto-dismissal
   - Ad/overlay/sticky header cleanup
   - Headline-anchored cropping
   ↓
2. PPTX Generator → 1-slide presentation
   - Template-matched element positioning (12 elements)
   - Smart font size fallback (14pt → 12pt → 11pt → 10pt)
   - Conditional bullets (plain text by default)
   - Auto-truncation for title & category
   ↓
3. Slide Validator → quality checks
   - Missing image / text overspill / blank fields
   - Captured image quality analysis (blank page / Cloudflare detection)
   - Writes issues to "Comments" column in Notion
   ↓
4. Notion Update
   - Checks "Slide Generated" checkbox
   - Sets "Slide Link" URL
   - Writes validation comments (or "All checks passed")
   ↓
Slide saved to ~/Desktop/slides/
```

## Quick Start

```bash
# 1. Clone/copy this folder to your Mac
# 2. Run setup
chmod +x setup.sh
./setup.sh

# 3. Edit .env with your Notion credentials
nano .env

# 4. Start server
source .venv/bin/activate
python main.py

# 5. Test
curl -X POST http://localhost:8000/test
```

## Batch Processing (CLI)

Process all unchecked articles from Notion in one command:

```bash
cd /Users/mridulmalani/Desktop/automation-system
source .venv/bin/activate
python main.py --batch
```

This queries the Notion database for all rows where "Slide Generated" is unchecked, processes each one through the full pipeline, and saves slides to `~/Desktop/slides/`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info + stats |
| `/health` | GET | Health check (Notion, template, dirs) |
| `/webhook/notion` | POST | Notion webhook receiver (signature-verified) |
| `/process` | POST | Manual single-article processing |
| `/process/batch` | POST | Process all unprocessed articles (API) |
| `/test` | POST | Generate test slide with sample data |
| `/stats` | GET | Processing statistics |
| `/docs` | GET | Auto-generated API docs (Swagger) |

## Manual Processing

```bash
# Process a specific article by Notion page ID
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{"page_id": "your-notion-page-id"}'

# Process with raw data (no Notion needed)
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Article Title",
    "summary": "Summary text...",
    "implications": "Main implication.\nSub-point 1.\nSub-point 2.",
    "category": "REGULATIONS",
    "source_url": "https://...",
    "credibility_score": 4,
    "relevancy_score": 3.5
  }'
```

## Features

### Smart Text Handling
- **Font size fallback**: Text boxes automatically choose the largest font that fits (14pt → 12pt → 11pt → 10pt) based on word count
- **Conditional bullets**: Summary text is plain paragraphs by default; only lines prefixed with `- ` render as bullets
- **Implications structure**: First line = plain paragraph, subsequent lines = arrow-bulleted sub-points (only if they exist)
- **Auto-truncation**: Title (90 chars) and category (25 chars) are truncated gracefully
- **normAutofit**: PowerPoint's built-in auto-shrink is enabled as a safety net on all content boxes

### Screenshot Capture (Selenium)
- **Cloudflare detection**: Detects "Just a moment" challenge pages and waits up to 15 seconds for resolution
- **Bot-detection avoidance**: Uses realistic user-agent, disables `navigator.webdriver` flag, removes automation indicators
- **Cookie banner dismissal**: Handles 30+ CMP frameworks (OneTrust, Quantcast, Didomi, Complianz, Iubenda, etc.) via CSS selectors + XPath text matching
- **Page cleanup**: Removes inline ads, sticky headers, iframes, sidebar widgets, and promotional elements
- **Headline-anchored cropping**: Finds the `<h1>` position and crops a 1400px region covering headline, hero image, and opening paragraph
- **Post-capture validation**: Checks for blank pages, missing headings, and very short body text

### Post-Generation Validation
After every slide is generated, an automated validator checks for:

| Check | What it catches |
|-------|----------------|
| Missing image | No screenshot captured (URL provided but capture failed, or no URL) |
| Image quality | Blank/single-color screenshot (Cloudflare page captured), suspiciously small files |
| Text overspill | Summary or implications exceeds hard word limit (220 words) |
| Font reduction | Word count exceeds recommended limit — font was reduced |
| Missing fields | Empty title, summary, or implications |
| Title truncation | Headline exceeded 90 chars |
| Category truncation | Category exceeded 25 chars |
| Missing date | Publication date missing (defaulted to today) |
| Missing source URL | No article URL provided |

Results are written to the **Comments** column in Notion. If all checks pass, it writes "All checks passed". Issues are listed as bullet points for easy triage.

### Notion Integration
- **Webhook receiver**: Validates `X-Notion-Signature` header, handles URL verification challenges
- **Field extraction**: Flexible property matching (handles various Notion column naming conventions)
- **Error text filtering**: Automatically filters out error messages from upstream AI evaluation (parsing failures, default scores, etc.)
- **Skips internal fields**: Client Rationale and Client Relevance columns are excluded (internal scraper feedback, not slide content)
- **Evaluation notes skipped**: Source assessment text is excluded from slides — star ratings come from numeric score columns
- **Batch pagination**: Handles Notion's 100-result-per-page limit for large databases

## Notion Database Setup

See **[NOTION_INPUT_GUIDE.md](NOTION_INPUT_GUIDE.md)** for detailed field constraints, word limits, and formatting rules.

### Required Fields

| Field | Type | Limit | Notes |
|-------|------|-------|-------|
| Name/Title | Title | 90 chars | Article headline |
| Summary | Rich Text | 120 words | Plain text; use `- ` prefix for bullets |
| Relevant Info | Rich Text | (shared with Summary) | Flows into same text box |
| Implications | Rich Text | 110 words | Line 1 = main point, rest = sub-bullets |
| Category | Select | 25 chars | REGULATIONS, M&A, GENERAL INNOVATION, etc. |
| Article URL | URL | — | Source article link |
| Source | Rich Text or Select | — | Publication name |
| Credibility | Number | 0-5 | Maps to 3-star rating |
| Relevance | Number | 0-5 | Maps to 3-star rating |
| Publication Date | Date | DD/MM/YYYY | Article date |
| Slide Generated | Checkbox | — | Auto-set by system |
| Slide Link | URL | — | Auto-set by system |
| Comments | Rich Text | — | Auto-set: validation results |

### Webhook Setup

1. Create a Notion integration at https://www.notion.so/my-integrations
2. Share your database with the integration
3. Configure webhook to point to `http://YOUR_MAC_IP:8000/webhook/notion`

## Star Rating Scale

Numeric scores (0-5) map to a 3-star visual:

| Score | Stars |
|-------|-------|
| 0.0 - 1.7 | 1 star |
| 1.8 - 3.3 | 2 stars |
| 3.4 - 5.0 | 3 stars |

## Auto-Start on Boot (macOS)

```bash
# Edit the plist file with your actual paths
nano com.exa.article-automation.plist

# Install
cp com.exa.article-automation.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.exa.article-automation.plist

# Check status
launchctl list | grep article-automation

# Stop
launchctl unload ~/Library/LaunchAgents/com.exa.article-automation.plist
```

## File Structure

```
automation-system/
├── main.py                    # FastAPI server + pipeline orchestrator
├── config.py                  # Configuration + template layout constants (EMUs)
├── modules/
│   ├── pptx_generator.py     # Slide generation from template (12 elements)
│   ├── selenium_capture.py   # Article screenshot capture (Selenium + Chrome)
│   ├── notion_client.py      # Notion API integration + Comments column
│   ├── slide_validator.py    # Post-generation quality checks
│   └── utils.py              # Helper functions (date formatting, retry, etc.)
├── templates/
│   └── slide_template.pptx   # Converted from .potx template
├── slides/                    # Generated slides output (or ~/Desktop/slides/)
├── logs/                      # Processing logs
├── cache/                     # Temporary image cache (auto-cleaned)
├── requirements.txt
├── .env.example
├── setup.sh
├── NOTION_INPUT_GUIDE.md      # Field constraints documentation
├── com.exa.article-automation.plist  # macOS auto-start
└── README.md
```

## Logs

Logs are written to `logs/automation.log` with timestamps and processing details.

```bash
# Watch logs in real time
tail -f logs/automation.log
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NOTION_API_KEY` | — | Notion integration API key |
| `NOTION_DATABASE_ID` | — | Notion database ID |
| `WEBHOOK_SECRET` | — | Webhook signature validation secret |
| `WEBHOOK_PORT` | 8000 | Server port |
| `SLIDES_OUTPUT_DIR` | `./slides` | Where generated .pptx files are saved |
| `ENVIRONMENT` | development | `development` enables auto-reload |
| `BROWSER_HEADLESS` | true | Run Chrome in headless mode |
| `BROWSER_TIMEOUT` | 30000 | Page load timeout (ms) |
