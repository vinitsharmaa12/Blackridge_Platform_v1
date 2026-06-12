"""Insight job runner retry and reset tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from insights.runner import process_job, reset_job_for_retry

JOB_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def _mock_cursor(fetchone_values: list) -> MagicMock:
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    cursor.fetchone.side_effect = fetchone_values
    return cursor


def test_reset_job_for_retry_returns_true_when_updated() -> None:
    conn = MagicMock()
    conn.cursor.return_value = _mock_cursor([("row-id",)])

    assert reset_job_for_retry(conn, JOB_ID) is True
    conn.commit.assert_not_called()


def test_reset_job_for_retry_returns_false_when_not_eligible() -> None:
    conn = MagicMock()
    conn.cursor.return_value = _mock_cursor([None])

    assert reset_job_for_retry(conn, JOB_ID) is False


@patch("insights.runner.run_agent")
@patch("insights.runner.build_client")
@patch("insights.runner.select_model")
@patch("insights.runner.connect")
@patch("insights.runner.get_insights_settings")
def test_process_job_runs_after_reset_from_failed(
    mock_settings: MagicMock,
    mock_connect: MagicMock,
    mock_select_model: MagicMock,
    mock_build_client: MagicMock,
    mock_run_agent: MagicMock,
) -> None:
    mock_settings.return_value = MagicMock(database_url="postgresql://test")
    conn = MagicMock()
    mock_connect.return_value.__enter__ = MagicMock(return_value=conn)
    mock_connect.return_value.__exit__ = MagicMock(return_value=False)

    job = {
        "id": JOB_ID,
        "instrument_id": 1,
        "symbol": "NIFTY",
        "user_id": JOB_ID,
        "trigger_type": "on_demand",
        "session_date": "2026-06-12",
        "status": "queued",
    }

    with patch("insights.runner._load_job", return_value=job), patch(
        "insights.runner.insight_already_written",
        return_value=False,
    ), patch("insights.runner._mark_job") as mock_mark, patch(
        "insights.runner.write_insight",
        return_value=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    ):
        from insights.schemas import AgentRunResult, InsightOutput

        mock_run_agent.return_value = AgentRunResult(
            output=InsightOutput(
                title="Test",
                narrative="PCR OI at 1.25.",
                sentiment_label="Neutral",
                confidence=0.8,
                cited_metrics={"pcr_oi": 1.25},
            ),
            model_id="google/gemini-flash",
            escalated=False,
        )
        result = process_job(JOB_ID)

    assert result is not None
    mock_mark.assert_any_call(conn, JOB_ID, status="running")
    mock_mark.assert_any_call(conn, JOB_ID, status="done")


@patch("insights.runner.connect")
@patch("insights.runner.get_insights_settings")
def test_process_job_skips_running_without_reset(
    mock_settings: MagicMock,
    mock_connect: MagicMock,
) -> None:
    mock_settings.return_value = MagicMock(database_url="postgresql://test")
    conn = MagicMock()
    mock_connect.return_value.__enter__ = MagicMock(return_value=conn)
    mock_connect.return_value.__exit__ = MagicMock(return_value=False)

    job = {
        "id": JOB_ID,
        "instrument_id": 1,
        "symbol": "NIFTY",
        "user_id": JOB_ID,
        "trigger_type": "on_demand",
        "session_date": "2026-06-12",
        "status": "running",
    }

    with patch("insights.runner._load_job", return_value=job):
        assert process_job(JOB_ID) is None


@patch("insights.runner.reset_job_for_retry")
@patch("insights.runner.connect")
@patch("insights.runner.get_insights_settings")
def test_reset_job_for_retry_by_id(
    mock_settings: MagicMock,
    mock_connect: MagicMock,
    mock_reset: MagicMock,
) -> None:
    from insights.runner import reset_job_for_retry_by_id

    mock_settings.return_value = MagicMock(database_url="postgresql://test")
    conn = MagicMock()
    mock_connect.return_value.__enter__ = MagicMock(return_value=conn)
    mock_connect.return_value.__exit__ = MagicMock(return_value=False)
    mock_reset.return_value = True

    assert reset_job_for_retry_by_id(JOB_ID) is True
    mock_reset.assert_called_once_with(conn, JOB_ID)
