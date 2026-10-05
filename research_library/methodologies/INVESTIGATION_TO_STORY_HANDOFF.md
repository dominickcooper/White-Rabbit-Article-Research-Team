# Investigation-to-story handoff

This methodology separates four functions even when one model performs them sequentially:

**RESEARCHER → SHOWRUNNER → WRITER → INDEPENDENT AUDITOR**

It is a boundary around context and authority, not a second instruction hierarchy.

## Researcher

The researcher reads the author brief and complete supported source corpus, locks the
Source Thesis before external research, retrieves published canon as established premises,
builds evidence and dependency-aware connection chains, pursues the three to five most
valuable rabbit holes, and records contradictions. The researcher does not choose a safer
adjacent article because it is easier to document.

## Thesis Lock and author checkpoint

The Source Thesis may be strengthened, refined, narrowed claim by claim, or contradicted.
It may not be silently replaced. A fundamental change requires the Story Decision to
record the original thesis, specific contrary evidence, failed claims, preserved research,
and proposed direction, then stop at **AUTHOR THESIS DECISION REQUIRED**. Strong contrary
evidence is never concealed and Thesis Lock is never permission to publish a false claim.

## Showrunner

The showrunner receives completed research and decides how to tell the assigned
investigation: opening receipt, reveal ladder, character bridges, delayed revelations,
earned tangent, cumulative inference, meaningful contradiction, payoff, and next door.
The showrunner does not select an unrelated investigation.

## Writer Packet

The showrunner produces `research/WRITER_PACKET.md`. It contains the locked thesis,
surviving findings, accepted testimony, canon premises, important characters, five to ten
connection chains, three to five investigated rabbit holes, crucial quotations and
locators, chronology, surprises, contradictions, factual boundaries, reveal sequence,
Story Spine, links, and relevant Gold voice behavior.

## Writer context

The writer primarily receives:

1. `research/SOURCE_THESIS.md`;
2. `research/WRITER_PACKET.md`;
3. `research/STORY_SPINE.md`;
4. selected documentary excerpts and source/link locators;
5. `research/STYLE_PROFILE.md` and relevant filtered Gold prose; and
6. publication/factual constraints.

The writer does not automatically receive the complete dossier, evidence ledger, Zebra
analysis, adversarial audit, abandoned hypotheses, or exploratory notes. Those remain
available only for a specific factual lookup. This keeps research bureaucracy out of the
narrator's voice without hiding evidence from the auditor.

## Independent auditor and surgical correction

The auditor receives the complete research record. Each finding must name the exact
passage or line, problem, supporting evidence, required factual constraint, and suggested
minimum correction. The auditor cannot change the locked thesis or freely rewrite prose.
The writer makes the surgical correction; the auditor rechecks factual accuracy.

## Preferred model roles and actual routing

When the execution environment offers them, the preferred roles are:

- research, extraction, connections, and evidence checking: **GPT-5.6 Sol High**;
- showrunning, drafting, and voice revision: **GPT-6 Astra**;
- independent factual/adversarial editing: **GPT-5.6 Sol High**;
- final surgical prose correction: **GPT-6 Astra**.

The repository's Codex-first CLI does not invoke or switch models. Run each named stage as
a separate Codex task/turn with the preferred model selected in the supported client, and
pass only the context defined above. The legacy Gemini pipeline continues to use its
configured provider model. No automatic cross-provider or unsupported model routing is
claimed.

