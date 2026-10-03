from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dart_agent_v2 import main  # noqa: E402

if __name__ == "__main__":
    main()
