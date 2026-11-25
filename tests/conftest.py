import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

from generate_sample_data import generate  # noqa: E402

from eda_assistant.data import from_frame  # noqa: E402
from eda_assistant.docs import DocumentIndex  # noqa: E402


@pytest.fixture(scope="session")
def dataset():
    return from_frame(generate(), name="heated_loop_run_042")


@pytest.fixture(scope="session")
def docs():
    return DocumentIndex.from_folder(ROOT / "examples" / "docs")
