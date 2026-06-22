import gzip
from pathlib import Path

_DATA = Path(__file__).parent / "data"


def load_fixture(name: str) -> str:
    path = _DATA / f"{name}.html.gz"
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        return fh.read()
