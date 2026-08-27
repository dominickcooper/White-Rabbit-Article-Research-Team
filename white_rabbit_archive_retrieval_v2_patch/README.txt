WHITE RABBIT ARCHIVE RETRIEVAL V2

Adds:
- non-destructive Substack boilerplate cleaning for search
- chunk-level indexing by section (~650 words)
- BM25 lexical ranking
- rare exact multi-word phrase/entity weighting
- local latent-semantic vectors using TF-IDF + TruncatedSVD (no Gemini/API credits)
- external research vs internal White Rabbit vs ignored-link classification
- WHY MATCHED diagnostics
- archive reindex command and automatic stale-index rebuild

Install from project root:
  Expand-Archive .\white_rabbit_archive_retrieval_v2_patch.zip -DestinationPath . -Force
  python .\white_rabbit_archive_retrieval_v2_patch\install_patch.py

Then test:
  python -m white_rabbit archive search "Flock Safety surveillance"
