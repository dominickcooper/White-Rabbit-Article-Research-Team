# SEO AND PUBLISHING STANDARDS

Create `output/seo.md` for every article.

## Required SEO/publishing fields

### Reader-Facing Title
Compelling, accurate, curiosity-driven. Ideally around 60–70 characters when practical, but do not damage a strong title to obey an arbitrary count.

### Reader-Facing Description / Sizzle
A short line or compact paragraph that sits beneath the article title and makes the reader want to continue. This is not the meta description.

### Meta Title
Aim for approximately 60 characters or fewer when practical.

### Meta Description
Aim for approximately 150–160 characters when practical. Clear, compelling, and accurate.

### URL Slug
Lowercase, hyphenated, concise, descriptive, no filler words when avoidable.

### Primary Keyword
One primary phrase.

### Secondary Keywords
A useful, non-stuffed list of supporting queries/entities.

### Social Share Title
A strong share-card title, which may be slightly punchier than the SEO title while remaining accurate.

### Social Share Description
Short and curiosity-driven.

### Hero/Banner Image Concept
The White Rabbit visual identity favors a dramatic late-1970s/1980s airbrush movie-poster montage aesthetic when generated art is appropriate.

The description should identify:
- central subject
- supporting figures/objects
- documentary/technical motifs
- era/location
- mood
- useful symbolism

Do not cram unrelated symbols into the banner merely because they appear somewhere in the article.

### Hero Image Alt Text
Describe the proposed image naturally and specifically. Include the main topic/entity when it genuinely describes the image. Do not keyword-stuff.

## In-article image markers
Insert useful visual placements directly into `article.md` using exactly:

`[IMAGE: <specific description> | ALT: <natural SEO-aware alt text>]`

Examples:
- `[IMAGE: Declassified FBI COINTELPRO memo with the "expose, disrupt, misdirect, discredit, or otherwise neutralize" language highlighted | ALT: Declassified FBI COINTELPRO memo describing disruption tactics]`
- `[IMAGE: Timeline connecting the FBI's 1956 launch of COINTELPRO, the 1971 Media burglary, and the Church Committee investigations | ALT: COINTELPRO timeline from 1956 through the Church Committee]`

Use roughly 5–10 image opportunities in a longer article when they materially help the reader.

Useful image types:
- archival photographs
- patent figures
- contract excerpts
- government-document snippets
- FOIA pages
- timelines
- relationship maps
- maps
- technical cutaways
- sensor/system diagrams
- historical newspaper excerpts

## Subscribe markers
Insert the exact marker:

`[[SUBSCRIBE]]`

Place between paragraphs/sections, never inside a paragraph.

Normally use about three placements:
- after the opening hook has delivered value;
- around the middle, preferably near a major reveal/transition;
- near the end before or after the conclusion/FAQ transition as appropriate.

Do not add generic subscription boilerplate around the marker unless the user requests custom CTA text.

## Share markers
Insert the exact marker:

`[[SHARE]]`

Use selectively after sections that contain a particularly surprising, useful, or discussion-worthy finding.

Do not interrupt the narrative every few paragraphs.

## Article title and deck in Markdown
`article.md` should normally begin:

`# READER-FACING TITLE`

followed by the reader-facing description/deck.

Main body sections should generally use `## ALL CAPS` headings.

## Keyword use
Use the primary keyword naturally in:
- the title when appropriate;
- the first ~100 words;
- at least one heading when natural;
- the body;
- the conclusion when natural.

Never keyword-stuff.
