"""Insights generate endpoint tests."""
from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient

from tests.api.conftest import TEST_USER_ID

JOB_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
SNAP_TIME = datetime(2026, 6, 8, 10, 30, tzinfo=UTC)

INST = {"id": 1, "symbol": "NIFTY"}

SAMPLE_INSIGHT = {
    "id": UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    "time": SNAP_TIME,
    "instrument_id": 1,
    "expiry": date(2026, 6, 9),
    "title": "NIFTY Neutral Positioning",
    "narrative": "PCR OI at 1.25 with underlying near 25000.",
    "sentiment_label": "Neutral",
    "confidence": 0.75,
    "cited_metrics": {"pcr_oi": 1.25, "underlying": 25000.0},
    "model": "google/gemini-test",
    "user_id": TEST_USER_ID,
}


def _mock_user_conn() -> AsyncMock:
    mock = AsyncMock()
    mock.__aenter__ = AsyncMock(return_value=object())
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


def test_generate_insight_queues_job(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    with patch(
        "apps.api.routers.insights.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.insights.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.insights.resolve_on_demand_job",
        new=AsyncMock(return_value=(JOB_ID, "queued")),
    ), patch(
        "apps.api.routers.insights.user_has_insight_today",
        new=AsyncMock(return_value=False),
    ), patch(
        "apps.api.routers.insights.asyncio.create_task",
    ) as mock_create_task:
        resp = client.post("/instruments/NIFTY/insights:generate", headers=auth_header)

    assert resp.status_code == 202
    body = resp.json()
    assert body["job_id"] == str(JOB_ID)
    assert body["status"] == "queued"
    mock_create_task.assert_called_once()


def test_generate_insight_retries_stuck_queued_job(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    with patch(
        "apps.api.routers.insights.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.insights.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.insights.resolve_on_demand_job",
        new=AsyncMock(return_value=(JOB_ID, "queued")),
    ), patch(
        "apps.api.routers.insights.user_has_insight_today",
        new=AsyncMock(return_value=False),
    ), patch(
        "apps.api.routers.insights.asyncio.create_task",
    ) as mock_create_task:
        resp = client.post("/instruments/NIFTY/insights:generate", headers=auth_header)

    assert resp.status_code == 202
    assert resp.json() == {"job_id": str(JOB_ID), "status": "queued"}
    mock_create_task.assert_called_once()


def test_generate_insight_retries_failed_job(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    with patch(
        "apps.api.routers.insights.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.insights.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.insights.resolve_on_demand_job",
        new=AsyncMock(return_value=(JOB_ID, "failed")),
    ), patch(
        "apps.api.routers.insights.user_has_insight_today",
        new=AsyncMock(return_value=False),
    ), patch(
        "apps.api.routers.insights.asyncio.create_task",
    ) as mock_create_task:
        resp = client.post("/instruments/NIFTY/insights:generate", headers=auth_header)

    assert resp.status_code == 202
    assert resp.json() == {"job_id": str(JOB_ID), "status": "retrying"}
    mock_create_task.assert_called_once()


def test_generate_insight_already_generated(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    with patch(
        "apps.api.routers.insights.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.insights.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.insights.resolve_on_demand_job",
        new=AsyncMock(return_value=(JOB_ID, "done")),
    ), patch(
        "apps.api.routers.insights.user_has_insight_today",
        new=AsyncMock(return_value=True),
    ), patch(
        "apps.api.routers.insights.asyncio.create_task",
    ) as mock_create_task:
        resp = client.post("/instruments/NIFTY/insights:generate", headers=auth_header)

    assert resp.status_code == 202
    assert resp.json() == {"job_id": str(JOB_ID), "status": "already_generated"}
    mock_create_task.assert_not_called()


def test_generate_insight_retries_done_without_insight(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    with patch(
        "apps.api.routers.insights.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.insights.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.insights.resolve_on_demand_job",
        new=AsyncMock(return_value=(JOB_ID, "done")),
    ), patch(
        "apps.api.routers.insights.user_has_insight_today",
        new=AsyncMock(return_value=False),
    ), patch(
        "apps.api.routers.insights.asyncio.create_task",
    ) as mock_create_task:
        resp = client.post("/instruments/NIFTY/insights:generate", headers=auth_header)

    assert resp.status_code == 202
    assert resp.json() == {"job_id": str(JOB_ID), "status": "retrying"}
    mock_create_task.assert_called_once()


def test_list_insights(
    client: TestClient,
    auth_header: dict[str, str],
) -> None:
    with patch(
        "apps.api.routers.insights.user_connection",
        return_value=_mock_user_conn(),
    ), patch(
        "apps.api.routers.insights.fetch_instrument",
        new=AsyncMock(return_value=INST),
    ), patch(
        "apps.api.routers.insights.fetch_insights",
        new=AsyncMock(return_value=[SAMPLE_INSIGHT]),
    ):
        resp = client.get("/instruments/NIFTY/insights?limit=5", headers=auth_header)

    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["title"] == SAMPLE_INSIGHT["title"]
    assert rows[0]["cited_metrics"]["pcr_oi"] == 1.25
    assert rows[0]["model"] == "google/gemini-test"
