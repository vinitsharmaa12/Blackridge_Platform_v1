"""API container build contract (PRD 005 slice 2)."""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "apps" / "api" / "Dockerfile"
RAILWAY_TOML = REPO_ROOT / "apps" / "api" / "railway.toml"


def test_api_dockerfile_declares_runtime_modules() -> None:
    text = DOCKERFILE.read_text(encoding="utf-8")
    for fragment in (
        "COPY apps/",
        "COPY core/",
        "COPY insights/",
        "COPY metrics.py",
        'CMD ["python", "-m", "apps.api"]',
        "USER blackridge",
    ):
        assert fragment in text


def test_api_railway_toml_wires_healthcheck() -> None:
    text = RAILWAY_TOML.read_text(encoding="utf-8")
    assert 'healthcheckPath = "/health"' in text
    assert 'startCommand = "python -m apps.api"' in text


def test_api_dockerfile_copies_exist_in_repo() -> None:
    for rel in ("apps/api", "core", "insights", "metrics.py", "requirements.txt"):
        assert (REPO_ROOT / rel).exists(), rel
