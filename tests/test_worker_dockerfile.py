"""Worker container build contract (PRD 005 slice 1)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "worker" / "Dockerfile"


def test_worker_dockerfile_declares_runtime_modules() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    for fragment in (
        "COPY core/",
        "COPY worker/",
        "COPY insights/",
        "COPY metrics.py",
        'CMD ["python", "-m", "worker"]',
        "USER blackridge",
    ):
        assert fragment in text


def test_worker_dockerfile_copies_exist_in_repo() -> None:
    for rel in ("core", "worker", "insights", "metrics.py", "requirements.txt"):
        assert (REPO_ROOT / rel).exists(), rel
