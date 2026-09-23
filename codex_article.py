"""Compatibility entry point for the local Codex article workspace."""

import sys

if __name__ == "__main__":
    from white_rabbit.codex_articles import main

    raise SystemExit(main())
else:
    from white_rabbit import codex_articles as _implementation

    # Preserve the historical `import codex_article` API while keeping the
    # implementation in white_rabbit.codex_articles.
    sys.modules[__name__] = _implementation
