import sys

if sys.argv[1:2] == ["distribution"]:
    from .distribution import main
    raise SystemExit(main(sys.argv[2:]))

from .cli import main

raise SystemExit(main())
