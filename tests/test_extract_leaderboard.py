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


def test_convert_hf_row_ignores_non_overall_categories():
    row = {
        "model_name": "gpt-5.5",
        "organization": "openai",
        "rating": 1553.57,
        "vote_count": 393.0,
        "category": "chinese",
    }

    assert extract_leaderboard._convert_hf_row(row) is None


def test_convert_hf_row_applies_model_organization_override():
    row = {
        "model_name": "dolphin-2.2.1-mistral-7b",
        "organization": "",
        "rating": 1080.99,
        "vote_count": 1679.0,
        "category": "overall",
    }

    assert extract_leaderboard._convert_hf_row(row)["organization"] == "Dolphin"


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

    records, last_updated = extract_leaderboard.fetch_latest_leaderboard_df()

    assert records == [
        {"Model": "model-a", "Score": "1400", "Votes": "1200", "organization": "OpenAI"},
        {"Model": "model-b", "Score": "1400", "Votes": "900", "organization": "Google"},
    ]
    assert last_updated == "2026-05-14"
