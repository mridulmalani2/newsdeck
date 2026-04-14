# Next Steps for Newsdeck Pipeline

## Overview
The News Article Slide Automation System currently generates slides from Notion database entries through manual batch processing. The following steps will fully automate the pipeline and improve query relevance over time.

---

## Step 1: Integrate Pipeline into n8n Workflow

**Objective**: Eliminate manual slide generation by running the batch processing as part of the n8n workflow.

### Setup Instructions

1. **Create output folder** on the n8n server:
   ```bash
   mkdir -p /opt/newsdeck-output/slides
   ```

2. **Update `.env`** to point to this folder:
   ```bash
   SLIDES_OUTPUT_DIR=/opt/newsdeck-output/slides
   ```

3. **In your n8n workflow**, add an "Execute Command" node:
   - Command: `cd /path/to/newsdeck && python main.py --batch`
   - Run this node at the end of your weekly workflow (after Notion population)
   - The batch process will automatically:
     - Query all unprocessed articles from Notion
     - Generate slides with screenshots
     - Update Notion with slide links and validation results

4. **Link Google Drive folder** to `/opt/newsdeck-output/slides`:
   - Use Google Drive's folder sync feature to sync the slides folder to your Drive
   - Slides will automatically appear in your Drive after each workflow run

### Result
Slides are generated automatically every week as part of your n8n workflow, with no manual intervention required.

---

## Step 2: Implement Dynamic Query Generation

**Objective**: Create a self-improving query system that maintains relevance over time by learning from past articles.

### Current State
- Queries are sourced from a Google Sheet
- Manually updated by client input
- No automatic refresh mechanism

### Desired State
- **Client direct input**: Manual updates to queries (existing method continues)
- **Automated query generation**: System learns from processed articles to suggest new queries

### Implementation Details

The system will work as follows:

1. **During article processing** (already happens):
   - Article marked as "relevant" in Notion
   - "Client Rationale" column stores explanation for why this article is relevant

2. **Query refresh mechanism** (to be built):
   - After each workflow run, analyze all articles marked as relevant
   - Extract patterns from their "Client Rationale" entries
   - Generate new search queries that capture similar trends and topics
   - Update the Google Sheet with suggested queries
   - Client can approve/modify before next workflow run

3. **Benefits**:
   - Keeps queries aligned with evolving industry trends
   - Automatically identifies new angles based on past relevance decisions
   - Reduces manual query maintenance
   - Improves article discovery over time

### Implementation Considerations
- Decide whether new queries replace old ones or supplement them
- Set up a review process for AI-generated queries before they're used
- Consider query history/versioning for audit trails

---

## Step 3: Improve Image Capture Quality (Low Priority - Shelved)

**Objective**: Enhance screenshot quality for articles from various source types.

### Current Limitations
Website scraping produces inconsistent image quality depending on source type and structure.

### Identified Solution
Implement category-specific scraping strategies:
- **Instagram links**: Custom scraping logic
- **YouTube articles**: Custom scraping logic
- **Quora answers**: Custom scraping logic
- **News articles**: Improved headline-focused cropping
- **Other URLs**: Generic Selenium capture

### Status
⏸️ **Shelved for later** — Complete Steps 1 & 2 first, then revisit this improvement.

---

## Timeline Suggestion
1. **Step 1**: 1-2 weeks (integration with n8n)
2. **Step 2**: 2-3 weeks (query generation system)
3. **Step 3**: Future (after Steps 1 & 2 are complete)

---

## Questions for Clarification
- [Add any team decisions or clarifications as they arise]
