from __future__ import annotations

from pathlib import Path

from agent_os.server.app import app


def _fresh_openapi() -> dict:
    app.openapi_schema = None
    return app.openapi()


def test_openapi_includes_bearer_security_and_servers():
    schema = _fresh_openapi()

    assert schema["servers"][0]["url"] == "http://localhost:8000"
    assert schema["servers"][1]["url"] == "https://demo.mydow.com"
    assert schema["components"]["securitySchemes"]["BearerAuth"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "Use the access_token returned by /api/v1/auth/login.",
    }

    capture = schema["paths"]["/api/v1/capture/text"]["post"]
    assert capture["security"] == [{"BearerAuth": []}]

    login = schema["paths"]["/api/v1/auth/login"]["post"]
    assert "security" not in login


def test_openapi_includes_prd10_request_response_examples():
    schema = _fresh_openapi()

    capture = schema["paths"]["/api/v1/capture/text"]["post"]
    capture_examples = capture["requestBody"]["content"]["application/json"]["examples"]
    assert capture_examples["inspiration"]["value"]["auto_process"] is True
    assert "source_url" in capture_examples["inspiration"]["value"]
    assert (
        capture["responses"]["200"]["content"]["application/json"]["examples"]["created"][
            "value"
        ]["data"]["inbox_item"]["tags"]
    )

    ai_stream = schema["paths"][
        "/api/v1/ai/conversations/{conversation_id}/messages/stream"
    ]["post"]
    assert "event: token" in (
        ai_stream["responses"]["200"]["content"]["application/json"]["examples"]["sse"][
            "value"
        ]
    )

    skill_run = schema["paths"]["/api/v1/skills/{skill_id}/run"]["post"]
    assert skill_run["requestBody"]["content"]["application/json"]["examples"]["run"][
        "value"
    ]["save_output"] is True


def test_openapi_includes_redoc_curl_code_samples_for_key_paths():
    schema = _fresh_openapi()

    required = [
        ("post", "/api/v1/auth/login"),
        ("post", "/api/v1/capture/text"),
        ("post", "/api/v1/kb/folders"),
        ("post", "/api/v1/ai/conversations"),
        ("post", "/api/v1/ai/conversations/{conversation_id}/messages/stream"),
        ("post", "/api/v1/skills/{skill_id}/run"),
        ("get", "/api/v1/search"),
    ]

    for method, path in required:
        samples = schema["paths"][path][method]["x-codeSamples"]
        assert samples[0]["lang"] == "cURL"
        assert "curl" in samples[0]["source"]
        assert path.replace("{conversation_id}", "<conversation_id>").replace(
            "{skill_id}", "<skill_id>"
        ) in samples[0]["source"]


def test_api_reference_documents_openapi_examples():
    content = Path("docs/11-deployment/api-reference.md").read_text(encoding="utf-8")

    assert "OpenAPI examples" in content
    assert "/api/v1/capture/text" in content
    assert "x-codeSamples" in content
