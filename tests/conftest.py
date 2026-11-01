import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_data: needs local, non-repository files (sample video, eval videos, SAM caches/probes, "
        "downloaded joint data). Core tests: pytest -m 'not real_data'.",
    )


def pytest_collection_modifyitems(config, items):
    # Every skipif in this suite guards on external files, so tag those tests as real_data.
    for item in items:
        if item.get_closest_marker("skipif") is not None:
            item.add_marker("real_data")
