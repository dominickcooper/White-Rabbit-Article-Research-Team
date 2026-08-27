WHITE RABBIT ARCHIVE RETRIEVAL v3
=================================

Targeted upgrade for Retrieval v2.

What changes
------------
1. Entity-aware query parsing
   "Flock Safety surveillance" becomes:
     primary named entity: Flock Safety
     secondary concept: surveillance
   The word "safety" is not independently rewarded just because it appears
   inside the named entity.

2. Entity gating / contrast scoring
   A result that does not contain the named entity must demonstrate a real
   conceptual or semantic connection. Generic "safety surveillance" matches
   are contrasted out, removing vaccine/drug-safety false positives.

3. Corpus-driven concept expansion
   The retriever learns related terms from chunks in the user's own White
   Rabbit archive that directly mention the entity. No Gemini call is used.

4. Canonical internal White Rabbit links
   Tracking/share parameters are removed. Junk anchors such as Share and Read
   full story are ignored. Internal candidates resolve back to the canonical
   archived article title and URL when that article exists locally.

5. New WHY MATCHED diagnostics
   Search output includes connection type, primary entity, related-concept
   score, and archive-derived concepts.

Install from project root
-------------------------
Expand-Archive .\white_rabbit_archive_retrieval_v3_patch.zip -DestinationPath . -Force
python .\white_rabbit_archive_retrieval_v3_patch\install_patch.py

Benchmark
---------
python -m white_rabbit archive search "Flock Safety surveillance"

Optional
--------
python -m white_rabbit archive search "Flock Safety surveillance" --limit 10 --links 10
python -m white_rabbit archive search "Flock Safety surveillance" --json

This patch does NOT redownload the Substack archive and does NOT call Gemini.
It builds archive_search_index_v3.joblib beside the existing knowledge DB.
