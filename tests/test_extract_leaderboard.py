import io
import json
from urllib.error import HTTPError

import pytest

from utils import extract_leaderboard


def test_convert_hf_row_maps_overall_leaderboard_schema():
    row = {
        "model_name": "claude-opus-4-6-thinking",
        "organization": "anthropic",
        "rating": 1499.6409,
        "vote_count": 25736.0,
        "category": "overall",
    }

    assert extract_leaderboard._convert_hf_row(row) == {
        "Model": "claude-opus-4-6-thinking",
        "Score": "1500",
        "Votes": "25736",
        "organization": "Anthropic",
    }


def test_convert_hf_row_maps_hyphenated_organization_ids():
    row = {"model_name": "mercury", "organization": "inception-ai", "rating": 1250.0, "category": "overall"}

    assert extract_leaderboard._convert_hf_row(row)["organization"] == "Inception AI"


def test_convert_hf_row_applies_model_organization_override():
    row = {
        "model_name": "dolphin-2.2.1-mistral-7b",
        "organization": "",
        "rating": 1080.99,
        "vote_count": 1679.0,
        "category": "overall",
    }

    assert extract_leaderboard._convert_hf_row(row)["organization"] == "Dolphin"


def test_visible_priced_models_have_blank_organization_overrides():
    for model_name, organization in {
        "intellect-3": "Prime Intellect",
        "trinity-large-thinking": "Arcee AI",
        "trinity-large-preview": "Arcee AI",
        "jamba-1.5-large": "AI21 Labs",
        "gemma-2-9b-it-simpo": "Princeton NLP",
        "reka-flash-20240904": "Reka",
        "openhermes-2.5-mistral-7b": "Teknium",
    }.items():
        row = {
            "model_name": model_name,
            "organization": "",
            "rating": 1200.0,
            "vote_count": 1000.0,
            "category": "overall",
        }

        assert extract_leaderboard._convert_hf_row(row)["organization"] == organization


def test_fetch_latest_leaderboard_stops_after_overall_category(monkeypatch):
    pages = {
        0: {
            "num_rows_total": 3,
            "rows": [
                {
                    "row": {
                        "model_name": "model-a",
                        "organization": "openai",
                        "rating": 1400.2,
                        "vote_count": 1200.0,
                        "rank": 1.0,
                        "category": "overall",
                        "leaderboard_publish_date": "2026-05-14",
                    }
                },
                {
                    "row": {
                        "model_name": "model-b",
                        "organization": "google",
                        "rating": 1399.6,
                        "vote_count": 900.0,
                        "rank": 2.0,
                        "category": "overall",
                        "leaderboard_publish_date": "2026-05-14",
                    }
                },
                {
                    "row": {
                        "model_name": "model-c",
                        "organization": "openai",
                        "rating": 1500.0,
                        "vote_count": 100.0,
                        "rank": 1.0,
                        "category": "chinese",
                        "leaderboard_publish_date": "2026-05-14",
                    }
                },
            ],
        }
    }

    monkeypatch.setattr(extract_leaderboard, "_fetch_rows_page", lambda offset: pages[offset])

    records, last_updated = extract_leaderboard.fetch_latest_leaderboard()

    assert records == [
        {"Model": "model-a", "Score": "1400", "Votes": "1200", "organization": "OpenAI"},
        {"Model": "model-b", "Score": "1400", "Votes": "900", "organization": "Google"},
    ]
    assert last_updated == "2026-05-14"


def _http_error(code):
    return HTTPError(extract_leaderboard.DATASET_ROWS_URL, code, "error", None, None)


def _stub_urlopen(monkeypatch, outcomes):
    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return io.BytesIO(json.dumps(outcome).encode("utf-8"))

    monkeypatch.setattr(extract_leaderboard, "urlopen", fake_urlopen)
    monkeypatch.setattr(extract_leaderboard.time, "sleep", lambda seconds: None)
    return calls


def test_fetch_rows_page_retries_server_errors(monkeypatch):
    payload = {"num_rows_total": 0, "rows": []}
    calls = _stub_urlopen(monkeypatch, [_http_error(502), payload])

    assert extract_leaderboard._fetch_rows_page(300) == payload
    assert len(calls) == 2


def test_fetch_rows_page_does_not_retry_client_errors(monkeypatch):
    calls = _stub_urlopen(monkeypatch, [_http_error(404)])

    with pytest.raises(HTTPError):
        extract_leaderboard._fetch_rows_page(0)
    assert len(calls) == 1


def test_fetch_rows_page_gives_up_after_last_attempt(monkeypatch):
    errors = [_http_error(502) for _ in range(extract_leaderboard.FETCH_ATTEMPTS)]
    calls = _stub_urlopen(monkeypatch, errors)

    with pytest.raises(HTTPError):
        extract_leaderboard._fetch_rows_page(0)
    assert len(calls) == extract_leaderboard.FETCH_ATTEMPTS
