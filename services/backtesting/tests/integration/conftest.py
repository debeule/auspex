import sys
from pathlib import Path

# The fixture filings and the fake SEC web server are shared with the unit tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit"))
