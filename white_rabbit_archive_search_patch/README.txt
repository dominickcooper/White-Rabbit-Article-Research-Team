White Rabbit Archive Search Patch

Adds:
  python -m white_rabbit archive search "QUERY"

Options:
  --limit N   max articles (default 8)
  --links N   max prior links per article (default 8)
  --json      machine-readable output

Retrieval is local/hybrid and does not spend Gemini credits. It weights title,
body relevance, phrase/bigram overlap, and prior hyperlink anchors.
