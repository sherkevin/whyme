"""Static contract checks for the VPS deployment handoff.

These tests do not deploy anything. They keep the public-runbook path
readable and make sure the preflight/smoke scripts still guard the
production no-mock requirements.
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = REPO_ROOT / "docs" / "11-deployment" / "cloud-vps-deploy.md"
PREFLIGHT = REPO_ROOT / "scripts" / "deploy" / "vps-preflight.sh"
SMOKE = REPO_ROOT / "scripts" / "deploy" / "vps-smoke.sh"


def test_cloud_vps_runbook_is_utf8_and_actionable() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "\u4e91\u670d\u52a1\u5668\u90e8\u7f72 Runbook" in text
    assert "Ubuntu 24.04 LTS VPS + Docker Compose + nginx + Let's Encrypt" in text
    assert "bash scripts/deploy/vps-preflight.sh .env" in text
    assert "bash scripts/deploy/vps-smoke.sh https://app.example.com" in text
    assert "docker compose --env-file .env -f docker-compose.prd10.yml --profile nginx up -d --build" in text
    assert "AGENTOS_AI_OFFLINE_PLACEHOLDER=off" in text
    assert "DEEPSEEK_API_BASE=https://api.deepseek.com" in text
    assert "\u5f53\u524d\u4ecd\u88ab\u5916\u90e8\u6761\u4ef6\u963b\u585e\u7684\u4e8b\u9879" in text


def test_cloud_vps_runbook_has_no_common_mojibake_fragments() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    # Guard against UTF-8 text being accidentally re-saved through a legacy
    # code page. These fragments appeared in the previous broken handoff doc.
    mojibake_markers = (
        "\u6d5c\u621e\u6e47",  # "浜戞湇"
        "\u9429\ue1c6\u723c",  # "鐩爣"
        "\u951b\u6c2d",  # "锛氬"
        "\u9286\u3000",  # "銆?"
        "\ufffd",
    )
    assert not any(marker in text for marker in mojibake_markers)


def test_vps_preflight_enforces_production_no_mock_guards() -> None:
    text = PREFLIGHT.read_text(encoding="utf-8")

    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "DEEPSEEK_API_KEY" in text
    assert "AGENTOS_DEMO_MODE" in text
    assert "AGENTOS_AI_OFFLINE_PLACEHOLDER" in text
    assert "AGENTOS_CORS_ALLOW_ALL" in text
    assert "docker compose --env-file \"$ENV_FILE\" -f \"$COMPOSE_FILE\" --profile nginx config --quiet" in text
    assert "copy it to the server deployment log folder" in text


def test_vps_smoke_checks_public_health_ready_and_frontend() -> None:
    text = SMOKE.read_text(encoding="utf-8")

    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "check /health 200" in text
    assert "check /ready 200" in text
    assert "${BASE_URL}/mydow/" in text
    assert "frontend marker found" in text
