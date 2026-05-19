# -*- coding: utf-8 -*-
"""Lightweight functional checks for the Flask app.

Run from this directory with:
    python regression_check.py
"""
import app as app_module
import app_smart_cards


async def _fake_agent_response(query, thread_id="test"):
    return f"fake agent response for {query} ({thread_id})"


def _assert_status(response, expected, name):
    assert response.status_code == expected, (
        f"{name}: expected {expected}, got {response.status_code}, "
        f"body={response.get_data(as_text=True)[:300]}"
    )


def main():
    app_smart_cards.get_agent_response = _fake_agent_response

    client = app_module.app.test_client()
    full_field = app_module.get_field_col("2024年科技投入")
    company = "中信信托"

    checks = [
        ("GET /", lambda: client.get("/"), 200),
        (
            "POST /api/analyze empty body",
            lambda: client.post("/api/analyze"),
            400,
        ),
        (
            "POST /api/chat-agent empty body",
            lambda: client.post("/api/chat-agent"),
            400,
        ),
        (
            "GET /api/company/field alias",
            lambda: client.get(
                "/api/company/field",
                query_string={"company": company, "field": "2024年科技投入"},
            ),
            200,
        ),
        (
            "GET /api/company/field full column",
            lambda: client.get(
                "/api/company/field",
                query_string={"company": company, "field": full_field},
            ),
            200,
        ),
        (
            "GET /api/query-smart full column",
            lambda: client.get(
                "/api/query-smart",
                query_string={"q": company + full_field},
            ),
            200,
        ),
        (
            "POST /api/cards/regenerate",
            lambda: client.post("/api/cards/industry_overview/regenerate", json={}),
            200,
        ),
    ]

    for name, call, expected in checks:
        response = call()
        _assert_status(response, expected, name)
        data = response.get_json(silent=True)
        if name == "GET /api/query-smart full column":
            assert data and data.get("success") is True, f"{name}: {data}"
            assert data.get("value") is not None, f"{name}: expected non-empty value"
        if name == "POST /api/cards/regenerate":
            assert data and data.get("result", "").startswith("fake agent response"), (
                f"{name}: {data}"
            )
        print(f"PASS {name}")


if __name__ == "__main__":
    main()
