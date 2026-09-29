# Codex semantic editorial-learning assignment: usaid-office-of-public-safety__part-05-operation-two-fold

This is Stage 2 of a Codex-first, no-provider-API workflow. Python prepared the comparison;
Codex must now perform the semantic editorial analysis.

Read these revision files completely:
- research_library/editorial_memory/revision_history/usaid-office-of-public-safety__part-05-operation-two-fold/draft_before_human_edit.md
- research_library/editorial_memory/revision_history/usaid-office-of-public-safety__part-05-operation-two-fold/final_published.md
- research_library/editorial_memory/revision_history/usaid-office-of-public-safety__part-05-operation-two-fold/editorial_diff.md

Read the permanent editorial/evidence standards:
- research_library/editorial_memory/VOICE_CANON.md
- research_library/editorial_memory/ANTI_PATTERNS.md
- research_library/editorial_memory/EDITORIAL_LESSONS.md
- research_library/editorial_memory/GOLD_ARTICLES.json
- docs/WHITE_RABBIT_STYLE.md
- docs/RESEARCH_AND_EVIDENCE.md
- series_projects/usaid-office-of-public-safety/shared_research/SERIES_THEMES.md
- series_projects/usaid-office-of-public-safety/SERIES_CONTINUITY.md
- series_projects/usaid-office-of-public-safety/articles/part-01-usaid-article/output/article.md
- series_projects/usaid-office-of-public-safety/articles/part-02-the-academy-and-the-agency/output/article.md
- series_projects/usaid-office-of-public-safety/articles/part-03-the-laboratory-countries/output/article.md
- series_projects/usaid-office-of-public-safety/articles/part-04-the-mitrione-problem/output/article.md

Comparison mode: `story_replacement`
Article identity outcome: `different_story` (score 0.080)
Draft title: USAID & THE CIA, PART 5: OPERATION TWO-FOLD
Final title: The Ban That Did Not End Police Aid

## Intentional story-replacement comparison

This pair is explicitly preserved as a story-replacement / series-scope comparison, not
an ordinary same-story editorial revision. Analyze why the selected story changed, but do
not infer that people, claims, sources, caveats or techniques deleted with the old story
were editorially rejected. Whole-story deletions are scope evidence only and must not
produce claim-level or global candidate learnings.


DO NOT merely summarize the textual diff. Determine the editorial reasoning implied by
the human changes. Distinguish direct textual evidence from careful inference. Quote only
short representative passages. Do not assume every human change is a reusable improvement.

## Required semantic analysis

### Story discovery
Determine whether the central mystery, thesis, larger pattern or actual story changed.

### Connection discovery
Identify added/promoted people, agencies, companies, programs, career paths and rabbit
holes—including connections research should have discovered before story architecture.

### Reveal order
Identify what moved earlier/later, became a reveal rather than background, was unburied,
or gained a better setup/payoff relationship.

### Evidence treatment
Identify caveats added/removed, attribution replacing qualification, changes in reliance
on named testimony, strengthened/weakened claims and changed evidentiary weight.

### Voice
Identify formal/academic/AI prose made conversational, narrator presence, transitions,
questions, concrete replacements for abstractions, paragraph rhythm and compression.

### Series continuity
Identify callbacks, conceptual payoffs, reused reader frameworks and changes to the next
installment handoff. If this is standalone, say not applicable.

### Ending
Determine whether recap became implication and whether the final question/rabbit hole changed.

### Repeated human preferences
Infer what the human consistently rejected and consistently added as principles—not a
catalog of individual word substitutions.

## Operation TWO-FOLD hypotheses to test

Test—do not assume—the following against the actual pair: personnel followed across
institutions; career paths used as institutional evidence; Garland Williams-type bridges;
the Swain / Tripodi / Baldwin chain; attributed participant testimony treated as evidence;
repetitive primary-source caveats reduced; the Anthony Triponi reversal preserved;
no-dismissals contradiction promoted; DEA prosecution/immunity connected to Part 3's
gatekeeper concept; research allowed to strengthen/change the thesis; explanation
compressed after the mechanism becomes clear. Reject any hypothesis the files do not support.

## Required outputs

Replace `research_library/editorial_memory/revision_history/usaid-office-of-public-safety__part-05-operation-two-fold/editorial_postmortem.md` with a substantive analysis using exactly
these level-two sections:

- EXECUTIVE FINDING
- WHAT THE ORIGINAL DRAFT GOT RIGHT
- WHAT CODEX MISSED
- THE STORY CHANGED
- CONNECTIONS THE HUMAN PROMOTED
- HOW EVIDENCE TREATMENT CHANGED
- HOW THE REVEAL ORDER CHANGED
- HOW THE VOICE CHANGED
- SERIES CALLBACKS AND PAYOFFS
- WHAT WAS CUT — AND WHY
- WHAT WAS ADDED — AND WHY
- REUSABLE LESSONS
- ARTICLE-SPECIFIC CHANGES THAT SHOULD NOT BECOME GLOBAL RULES
- QUESTIONS FOR HUMAN REVIEW

Analysis comes first; leave only genuinely ambiguous items as questions.

Replace `research_library/editorial_memory/revision_history/usaid-office-of-public-safety__part-05-operation-two-fold/candidate_learnings.json` with valid JSON using this shape:

```json
{
  "schema_version": 2,
  "key": "usaid-office-of-public-safety__part-05-operation-two-fold",
  "analysis_status": "analyzed",
  "automatic_promotion": false,
  "candidate_learnings": [
    {
      "id": "short-stable-id",
      "category": "CONNECTION_ADDED",
      "lesson": "A reusable imperative lesson.",
      "evidence": "Concise article-specific evidence from the comparison.",
      "scope": "global",
      "confidence": "high",
      "status": "pending",
      "promote_to": "EDITORIAL_LESSONS.md"
    }
  ]
}
```

Allowed categories: CAVEAT_ADDITION, CAVEAT_REMOVAL, COMPRESSION, CONCLUSION, CONNECTION_ADDED, EXPANSION, EXPLANATION, FACTUAL_CORRECTION, FORMATTING, FRAMING_CHANGE, PERSONNEL_RABBIT_HOLE, RESEARCH_DISCOVERY, REVEAL_ORDER, SEO, SERIES_CALLBACK, SOURCE_TREATMENT, STRONGER_INFERENCE, STRUCTURE, VOICE, WEAKER_INFERENCE.
Allowed scopes: global, investigative, series, article-specific. Article-specific items
normally stay unpromoted. Allowed confidence: high, medium, low. Every candidate starts
pending. Never mark a candidate approved; approval belongs to the human. Never edit
VOICE_CANON.md, ANTI_PATTERNS.md or EDITORIAL_LESSONS.md in this analysis pass.

When both files are written, run `python codex_article.py learning-status usaid-office-of-public-safety__part-05-operation-two-fold` and
report the status. Do not run promote-learnings.
