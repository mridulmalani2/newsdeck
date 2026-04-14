# Newsdeck Automation System - PPT Creation Guidelines

**Project**: Create a 6-slide presentation explaining the Newsdeck F1 Article Automation System
**Audience**: Internal stakeholders / Project team
**Duration**: ~2-3 minutes of narration per presentation
**Format**: Professional PowerPoint presentation

---

## BRANDING & DESIGN GUIDELINES

### Critical Instructions for This Project

**You have been provided with existing PPT screenshots showing brand examples.** Before creating any slide, you MUST:

1. **Review all provided PPT samples** to understand:
   - Font families, sizes, and weights used (serif vs. sans-serif)
   - Color palette and accent colors
   - Cover page layout and structure
   - Content slide layouts and information hierarchy
   - Element placement (headers, footers, logos, badges)
   - Icon styles and visual treatments

2. **Follow these brand principles consistently**:
   - Use the exact same fonts as shown in examples (font stack required from samples)
   - Maintain color consistency with provided palette
   - Mirror the layout patterns from cover pages and content slides
   - Use similar icon styles and visual elements
   - Keep consistent margins, spacing, and alignment
   - Match the professional tone and aesthetic

3. **Assets to Use**:
   - All logos, icons, and graphics visible in provided samples
   - Color codes from existing designs
   - Exact typography (font names, sizes, weights)
   - Header/footer treatments
   - Any design elements or backgrounds shown in samples

4. **Consistency is Critical**:
   - Every slide should feel like it belongs to the same presentation
   - If sample slides use specific diagram styles, replicate that treatment
   - If tables/data visualization is shown in samples, match that approach
   - Maintain the visual hierarchy and emphasis techniques shown

---

## PRESENTATION STRUCTURE: 6 SLIDES TOTAL

### SECTION A: CURRENT SYSTEM (Slides 1-3)

#### SLIDE 1: Cover/Title Slide

**Purpose**: Introduce the Newsdeck automation system and set expectations

**Content to Include**:
- **Main Title**: "Newsdeck Automation"
- **Subtitle**: "F1 Technology Article Intelligence Pipeline"
- **Brief descriptor**: "Automated Discovery, Analysis & Curation System"
- Optional: Add a key stat (e.g., "Processing 50+ articles weekly", "3-tier AI evaluation")

**Design Notes**:
- Use the cover page template/style from provided samples
- Prominent placement of project title
- Professional, clean design
- Include any project badges or certification marks if shown in samples

**What NOT to do**:
- Don't make it look like a technical spec document
- Avoid cluttering with details
- No small text or complex diagrams

---

#### SLIDE 2: Current System Overview & n8n Workflow

**Purpose**: Show HOW the current system works (the n8n workflow pipeline)

**Key Information to Visualize**:

The workflow has these main stages (in order):

1. **Trigger** (Weekly Schedule or Manual)
   - Runs every Monday at 9 AM
   - Can also be triggered manually via webhook

2. **Input: Search Queries**
   - Queries are stored in a Google Sheet
   - One row = one search topic (e.g., "F1 regulations 2026", "Mercedes aerodynamics")

3. **Web Search & Discovery**
   - Uses SerpAPI to search Google for articles
   - Fetches 10 results per query, last 30 days
   - All results are deduplicated (removes duplicates across queries)

4. **Filtering Loop** (For Each Article):
   - Check if URL already exists in Notion database
   - Skip if duplicate / already processed

5. **AI Analysis** (Multi-Agent):
   - **Agent 1**: OpenAI GPT-4o Summarizer → Creates 120-word summary
   - **Agent 2**: Article Evaluator → Scores: Credibility (1-5), Accuracy (1-5), Relevance (1-5), Overall (1-5)
   - **Agent 3**: Theme Classifier → Assigns primary theme + up to 5 sub-themes
   - **Agent 4**: Implication Analyzer → Generates key implications (110 words)

6. **Quality Gate**:
   - Filter: Keep only articles with Overall Score >= 3
   - Discard low-quality articles

7. **Data Validation**:
   - Enforce Notion field constraints:
     - Title: max 90 characters
     - Category: max 25 characters
     - Summary + Relevant Info: max 220 words combined
     - Scores: clamped 0-5 range

8. **Save to Notion**:
   - All validated article data stored in Notion database
   - Fields include: Title, URL, Summary, Themes, Scores, Implications, Analysis Date

**How to Present**:
- Create a **flow diagram** showing the pipeline stages
- Use boxes/shapes for each major stage
- Use arrows to show data flow
- Color-code by function:
  - Input/Trigger (one color)
  - Search & Discovery (another color)
  - AI Analysis (another color)
  - Output/Storage (another color)
- Keep it linear, left-to-right or top-to-bottom

**Key Metric to Highlight**:
- Weekly: 5-8 queries → 50-80 articles found → ~30-40 qualify (40-50% pass quality gate) → stored in Notion

---

#### SLIDE 3: Data Quality & Field Management

**Purpose**: Explain HOW data is validated and organized

**Content to Include**:

**Three AI Evaluation Scores**:
| Score | What It Measures | Scale |
|-------|-----------------|-------|
| Credibility | Is the source trustworthy? (5=FIA/major outlet, 1=unknown) | 1-5 |
| Accuracy | Are the claims factually correct? (5=official/verified, 1=misinformation) | 1-5 |
| Relevance | How relevant to F1 R&D? (5=deep technical, 1=not related) | 1-5 |

**Theme Categories** (from classified article themes):
- Aerodynamics
- Power Unit
- Chassis & Suspension
- Electronics & Software
- Materials & Manufacturing
- Testing & Simulation
- Regulations & Compliance
- Race Strategy Tech
- Driver Interface
- Safety Innovations
- Cooling Systems
- Data Analysis
- Team Collaboration
- Sustainability
- General Innovation

**Field Constraints**:
- Title: ≤ 90 characters (auto-truncated)
- Category: ≤ 25 characters (normalized to uppercase)
- Summary + Relevant Info: ≤ 220 words combined (auto-truncated if needed)
- Publication Date: Stored in YYYY-MM-DD format
- All scores: Clamped to 0-5 range

**Storage Location**: Notion Database
- Every article that passes quality gates (score ≥ 3) is saved
- Fields auto-populate from AI analysis
- Ready for downstream processing

**How to Present**:
- Use a **table or structured layout** to show the scoring system
- Show sample theme tags/pills to visualize categorization
- Display field constraints as visual limits (e.g., character count bars)
- Use icons or colors to differentiate score levels (green for high, yellow for medium, red for low)

---

### SECTION B: NEXT STEPS / ROADMAP (Slides 4-6)

#### SLIDE 4: Step 1 - Integrate Slide Generation Pipeline

**Purpose**: Explain how the current system will be enhanced by adding automated slide generation

**The Problem Being Solved**:
- Currently: Articles are stored in Notion, but no slides are generated
- Manual process: Someone runs batch processing on a local machine to create slides
- Goal: Automate this completely so slides are generated as part of the n8n workflow

**The Solution - n8n Integration**:

The n8n workflow will be extended to include a new node at the end:

1. **Execute Command Node** in n8n:
   - After Notion article is saved
   - Triggers: `python main.py --batch`
   - Runs on n8n server (not your laptop)

2. **What Happens**:
   - Queries Notion for all unprocessed articles
   - For each article:
     - Captures screenshot of article webpage (Selenium + Chrome)
     - Generates professional 1-slide PowerPoint using template
     - Validates screenshot quality
     - Creates backup slides (viewport + full-page screenshots)
     - Validates output quality
   - All slides saved to: `/opt/newsdeck-output/slides`

3. **Output Delivery**:
   - Slides folder is **synced to Google Drive**
   - Results appear automatically in Drive after each workflow run
   - No manual file management needed

**Benefits**:
- Fully automated: No laptop or manual intervention required
- Weekly execution: Slides generated automatically every Monday at 9 AM
- Quality assured: Validation checks catch errors before storage
- Drive accessible: Slides immediately available in Google Drive

**Technical Details** (for reference):
- Slide generation uses Python PPTX library with custom template
- Screenshot capture uses Selenium + ChromeDriver
- Validates image quality (detects blank pages, Cloudflare challenges)
- Updates Notion with "Slide Generated" checkbox + slide link

**How to Present**:
- Show **before/after**: Manual process vs. automated process
- Highlight the **new n8n node** in the pipeline
- Use icons to show: Article → Screenshot → Slide → Google Drive
- Emphasize the **elimination of manual work**

---

#### SLIDE 5: Step 2 - Dynamic Query Generation System

**Purpose**: Explain how queries will become self-improving and stay relevant over time

**The Problem Being Solved**:
- Currently: Search queries are static (stored in Google Sheet, manually updated)
- Manual overhead: Client must manually update queries to catch new trends
- Goal: System learns from past articles and automatically suggests new queries

**The Solution - Automated Query Refresh**:

Two sources of search queries:

**Source 1: Client Direct Input** (Existing)
- User manually adds/updates queries in Google Sheet
- Examples: "F1 aerodynamics 2026", "Mercedes DRS system", "fuel cell technology"
- Always honored and used in workflow

**Source 2: Automated Generation** (New - Based on Past Articles)
- System analyzes articles marked as "relevant" by client
- Extracts "Client Rationale" field from each relevant article
  - Example rationale: "New regulations could impact suspension geometry"
  - Another example: "Mercedes' cooling system approach affects team competitiveness"
- Uses AI to identify **patterns and trends** in these rationales
- Automatically generates new search queries that capture similar topics
- Updates Google Sheet with suggested queries
- Client reviews and approves before next workflow run

**How It Works**:
1. Article processed → Client marks as "relevant" → Rationale captured
2. (Weekly) Analyze all relevant articles from past month
3. Extract common themes and topics from their rationales
4. Generate new search queries that match these themes
5. Suggest to client: "Based on recent articles, consider searching..."
6. Client approves/modifies → Added to Google Sheet
7. Next workflow run uses both manual + auto-generated queries

**Example**:
- Past articles about "brake systems" are marked relevant
- Rationales mention "cooling efficiency" and "thermal management"
- System suggests new queries: "F1 thermal management innovation", "brake cooling 2026"
- Client approves → Added to search list

**Benefits**:
- Stays relevant: Always searching for articles matching current interests
- Reduces manual work: No manual query updates needed
- Trend detection: Automatically catches emerging topics
- Historical continuity: Learns from past decisions

**How to Present**:
- Show **query feedback loop**: Articles → Rationales → New Queries → Back to Search
- Create a sample visualization of how rationales inform query generation
- Use a comparison: "Old way (manual)" vs. "New way (automatic + manual)"
- Emphasize the **learning aspect**: System improves over time

---

#### SLIDE 6: Step 3 - Image Capture Quality Improvements (Future/Shelved)

**Purpose**: Explain the planned enhancement to handle different article sources

**Status**: ⏸️ **Low Priority - Shelved for After Steps 1 & 2**

**The Problem**:
- Current screenshot capture (Selenium) works but has limitations
- Different websites have different structures:
  - Social media (Instagram, TikTok): No traditional articles
  - Video platforms (YouTube): No direct article snapshots
  - Forums (Quora, Reddit): Conversation-based, not articles
  - News sites: Well-structured articles
- Current approach treats all sources the same → inconsistent quality

**The Planned Solution**:
Implement **category-specific scraping strategies**:

| Source Type | Current Issue | Planned Treatment |
|-------------|---------------|-------------------|
| **Instagram** | Image-only posts, no article text | Extract post caption + images, preserve layout |
| **YouTube** | Video content, no screenshot | Extract video thumbnail + description |
| **Quora** | Threaded discussion format | Extract top answer + question, preserve hierarchy |
| **Twitter/X** | Short-form tweets, threading | Capture thread as connected posts |
| **News Sites** | Various templates, different designs | Headline-focused crop (already working) |
| **Blogs** | Varied layouts, sidebars, ads | Intelligent content extraction, skip cruft |

**Why Shelved**:
- Complexity: Each source type requires custom logic
- Current system works: Selenium captures basic screenshots successfully
- Priority order: Complete Steps 1 & 2 first (larger impact)
- Dependency: Better to refine slides + queries first

**When to Revisit**:
- After Step 1 & 2 are implemented and stable
- If quality issues with specific source types become blocking
- If social media articles become a larger portion of relevant content

**How to Present**:
- Show **current coverage**: Works well for news/blogs, limited for social
- Display a **table** of source types and their treatments
- Use a **timeline/roadmap** visual showing priorities:
  1. Step 1: Slides (highest priority)
  2. Step 2: Queries (high priority)
  3. Step 3: Image Quality (future enhancement)
- Position as "optimization for later, not blocking current goals"

---

## VISUAL DESIGN RECOMMENDATIONS

### Color Palette (Match to Provided Samples)
- **Primary**: [Extract from provided PPT samples]
- **Secondary**: [Extract from provided PPT samples]
- **Accent**: [Extract from provided PPT samples]
- **Background**: [Extract from provided PPT samples]

### Typography (Must Match Provided Samples)
- **Headlines**: [Font name, size, weight from samples]
- **Body text**: [Font name, size, weight from samples]
- **Accent/callout**: [Font name, size, weight from samples]

### Element Style Guide (From Provided Samples)
- **Boxes/Containers**: [Style shown in examples]
- **Icons**: [Style shown in examples]
- **Tables/Data**: [Style shown in examples]
- **Callouts/Emphasis**: [Style shown in examples]
- **Arrows/Connectors**: [Style shown in examples]

---

## SLIDE-BY-SLIDE CHECKLIST

### Slide 1 ✓
- [ ] Title and subtitle clearly visible
- [ ] Professional, clean cover design
- [ ] Matches provided cover page template
- [ ] No small text or clutter
- [ ] Brand colors and fonts correct
- [ ] Logo placement matches samples

### Slide 2 ✓
- [ ] Shows clear 8-stage pipeline flow
- [ ] Uses boxes/shapes for each stage
- [ ] Color-coded by function (4 color categories)
- [ ] Arrows show data direction
- [ ] Readable labels for each stage
- [ ] Matches diagram style from samples
- [ ] Flows logically (left-to-right or top-to-bottom)

### Slide 3 ✓
- [ ] Three scoring criteria clearly displayed (Credibility, Accuracy, Relevance)
- [ ] Theme categories listed (15 themes shown)
- [ ] Field constraints visualized (character limits, word limits)
- [ ] Table or structured layout (not walls of text)
- [ ] Icons/colors for score levels (green/yellow/red)
- [ ] Notion database mentioned as storage

### Slide 4 ✓
- [ ] Shows problem: "Manual slides required laptop"
- [ ] Shows solution: "n8n integration + automated execution"
- [ ] Highlights new workflow step (Execute Command node)
- [ ] Icons show: Article → Screenshot → Slide → Google Drive
- [ ] Benefits listed (automated, weekly, quality, drive-accessible)
- [ ] No technical jargon (accessible to non-engineers)

### Slide 5 ✓
- [ ] Shows query feedback loop clearly
- [ ] Two sources of queries distinguished:
  - [ ] Client direct input (manual)
  - [ ] Automated generation (from past articles)
- [ ] Rationale concept explained with examples
- [ ] Sample flow visualization: Articles → Rationales → New Queries
- [ ] Benefits highlighted (relevance, reduced work, trend detection)
- [ ] Timeline/cycle shown

### Slide 6 ✓
- [ ] Status clearly marked: "⏸️ Low Priority - Shelved"
- [ ] Problem explained: "Different sources need different treatments"
- [ ] Table shows source types and planned treatments
- [ ] Timeline/roadmap shows priority (Steps 1-2 first, Step 3 later)
- [ ] Clear on "why shelved" and "when to revisit"
- [ ] Not presented as blocking or incomplete

---

## FINAL NOTES FOR CLAUDE COWORK

1. **You have everything you need**: 
   - This markdown with full context and content
   - PPT sample screenshots showing brand, fonts, colors, layouts
   - Clarity on what each slide should contain

2. **Your job is to**:
   - Create 6 slides following this structure
   - Use fonts, colors, and styles from provided sample PPTs
   - Make diagrams/visuals that match the brand aesthetic
   - Ensure consistency across all slides

3. **Quality checks**:
   - Read through all 6 slides as a cohesive story
   - Verify each slide's checklist items are complete
   - Confirm colors and fonts match samples throughout
   - Ensure no jargon that would confuse non-technical viewers
   - Check alignment and spacing match the professional examples

4. **If you have questions**:
   - Reference the provided PPT samples for design guidance
   - This markdown contains all content and context needed
   - Trust the branding from examples; replicate consistently

---

**Good luck! This presentation should tell a complete story of the system, current state, and exciting future improvements.**
