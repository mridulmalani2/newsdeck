# News Article Slide Automation System

Webhook-triggered automation that processes F1/motorsport news articles from a Notion database, generates professionally designed PPTX slides matching the Project F template, and updates Notion with slide links.

## Architecture

```
Notion DB (new row) → Webhook → FastAPI Server → [Playwright + PPTX Generator] → Slide saved + Notion updated
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

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Server info + stats |
| `/health` | GET | Health check |
| `/webhook/notion` | POST | Notion webhook receiver |
| `/process` | POST | Manual single-article processing |
| `/process/batch` | POST | Process all unprocessed articles |
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

## Notion Database Setup

### Required Fields

| Field | Type | Notes |
|-------|------|-------|
| Name/Title | Title | Article headline |
| Summary | Rich Text | Summary bullets (newline-separated) |
| Implications | Rich Text | First line = main point, rest = sub-bullets |
| Category/Primary Theme | Select | REGULATIONS, M&A, COMPETITIVE MOVE, etc. |
| Article URL | URL | Source article link |
| Source | Rich Text or Select | Publication name |
| Credibility | Number | 0-5 scale |
| Relevancy | Number | 0-5 scale |
| Publication Date | Date | Article date |
| Slide Generated | Checkbox | Auto-set by system |
| Slide Link | URL | Auto-set by system (file:// path) |

### Webhook Setup

1. Create a Notion integration at https://www.notion.so/my-integrations
2. Share your database with the integration
3. Configure webhook to point to `http://YOUR_MAC_IP:8000/webhook/notion`

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
├── main.py                    # FastAPI server + orchestrator
├── config.py                  # Configuration + template layout constants
├── modules/
│   ├── pptx_generator.py     # Slide generation from template
│   ├── playwright_capture.py # Article screenshot capture
│   ├── notion_client.py      # Notion API integration
│   └── utils.py              # Helper functions
├── templates/
│   └── Project_F_Update_20250429-FinalVersion.pptx
├── slides/                    # Generated slides output
├── logs/                      # Processing logs
├── cache/                     # Temporary image cache
├── requirements.txt
├── .env.example
├── setup.sh
├── com.exa.article-automation.plist  # macOS auto-start
└── README.md
```

## Star Rating Scale

Numeric scores (0-5) map to a 3-star visual:

| Score | Stars |
|-------|-------|
| 0.0 - 1.7 | ★☆☆ |
| 1.8 - 3.3 | ★★☆ |
| 3.4 - 5.0 | ★★★ |

## Logs

Logs are written to `logs/automation.log` with timestamps and processing details.

```bash
# Watch logs in real time
tail -f logs/automation.log
```
