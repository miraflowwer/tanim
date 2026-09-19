import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.service import GrciRequestHandler


class handler(GrciRequestHandler):
    """Expose the existing TANIM service through one Vercel route."""

    pass
