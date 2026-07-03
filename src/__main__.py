import sys
from pathlib import Path

import uvicorn

# Under `python -m src`, the repo root is on sys.path but src/ is not, so the
# top-level module `api` (src/api) is not importable by name. Put src/ on the
# path so `from api import app` resolves the same way it does under pytest.
_SRC_DIR = str(Path(__file__).resolve().parent)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from api import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
