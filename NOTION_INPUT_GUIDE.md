# Notion Input Guide — Slide Automation

Field constraints for the Notion database that feeds the slide automation pipeline. Following these limits ensures clean, readable 1-slider output without any manual adjustment.

## Field Reference

### Title (Article Headline)
- **Max:** 90 characters
- **Font:** 20pt bold, auto-shrinks if over
- Appears as the main headline across the top of the slide
- If over 90 chars, it will be truncated with "..."
- Aim for clear, concise headlines

### Category
- **Max:** 25 characters
- **Font:** 12pt, centered in red box
- Displayed in the top-left red tag
- Use uppercase (auto-converted): `REGULATIONS`, `M&A`, `GENERAL INNOVATION`, etc.
- If over 25 chars, truncated with "."

### Publication Date
- **Format:** `DD/MM/YYYY` (preferred) or `YYYY-MM-DD`
- Displayed below the category tag
- Auto-formatted to DD/MM/YYYY
- If empty, defaults to current date

### Summary + Relevant Information
- **Recommended:** 120 words combined (both fields together)
- **Hard limit:** 220 words (font shrinks to 10pt — still readable but tight)
- **Font:** 14pt default → 12pt → 11pt → 10pt (auto-fallback based on length)
- Plain text paragraphs by default — no bullets
- Use newlines to separate distinct points
- **To add bullet points:** prefix lines with `- ` (dash + space) — only those lines become bullets
- The summary and relevant info flow together in one text box

#### Summary field
Write as flowing text. Separate distinct thoughts with newlines.

Example (no bullets):
```
Mercedes has strongly opposed proposed changes to the 2026 F1 engine regulations.
The proposals aim to adjust the 50/50 power split between ICE and electric power during races.
```

Example (with sub-points):
```
Mercedes has strongly opposed proposed changes to the 2026 F1 engine regulations.
- The proposals aim to adjust the 50/50 power split
- Other teams like McLaren are open to discussions
```

#### Relevant Information field
Same rules as summary. Both fields share the same text box and word budget.

### Implications
- **Recommended:** 110 words total (main point + all sub-points combined)
- **Hard limit:** 220 words
- **Font:** Same 14pt → 10pt fallback as summary
- **Structure:** First line = main implication (plain text, no bullet). Subsequent lines = sub-points (automatically get arrow bullets)

Example:
```
Mercedes' strong opposition underscores potential instability in F1's technical direction.
Such instability could deter OEMs seeking a predictable investment environment.
Divergent views among teams may signal a lack of consensus.
```

This renders as:
- Line 1 → plain paragraph
- Lines 2-3 → arrow-bulleted sub-points (only because they exist)

If there's only one line, it renders as a plain paragraph with no bullets at all.

### Source URL
- Full URL to the source article
- Displayed at the bottom with a clickable hyperlink
- Long URLs (>120 chars) are truncated in display but the full link works

### Credibility Score
- **Range:** 0 to 5 (decimal allowed)
- Displayed as 3-star rating:
  - 0.0–1.7 → 1 star
  - 1.8–3.3 → 2 stars
  - 3.4–5.0 → 3 stars

### Relevance Score
- Same scale and mapping as Credibility

### Article Image
- Optional — a single image representing the article
- Displayed on the left side of the slide
- If no image is available, the image area is left clean (no placeholder)
- Automatically cropped to fit the slot without distortion

## Categories (Select Field)

Recommended values (all auto-uppercased):
- `REGULATIONS`
- `M&A`
- `COMPETITIVE MOVE`
- `PERFORMANCE`
- `GENERAL INNOVATION`
- `TESTING & SIMULATION`
- `COOLING SYSTEMS`
- `AERODYNAMICS`

Keep new categories under 25 characters.

## Quick Checklist

| Field | Target | Max | What happens if exceeded |
|-------|--------|-----|--------------------------|
| Title | ~60 chars | 90 chars | Truncated with "..." |
| Category | ~18 chars | 25 chars | Truncated with "." |
| Summary + Relevant Info | ~120 words | 220 words | Font shrinks to 10pt |
| Implications | ~110 words | 220 words | Font shrinks to 10pt |
| Credibility | 0–5 | 5 | Capped at 3 stars |
| Relevance | 0–5 | 5 | Capped at 3 stars |
