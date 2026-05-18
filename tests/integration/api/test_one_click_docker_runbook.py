from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = REPO_ROOT / "docs" / "11-deployment" / "one-click-docker.md"
PS_LAUNCHER = REPO_ROOT / "scripts" / "run_mydow_docker.ps1"
BASH_LAUNCHER = REPO_ROOT / "scripts" / "run_mydow_docker.sh"
CMD_WRAPPER = REPO_ROOT / "run-mydow.cmd"
SH_WRAPPER = REPO_ROOT / "run-mydow.sh"
CODEX_PROMPT = REPO_ROOT / "docs" / "11-deployment" / "codex-local-run-prompt.md"


def test_one_click_runbook_documents_full_local_stack() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "http://localhost:8080/" in text
    assert "nginx -> FastAPI app -> Postgres 16" in text
    assert "DEEPSEEK_API_KEY" in text
    assert "LLM_BASE_URL" in text
    assert "LLM API URL" in text
    assert ".env.docker.local" in text
    assert "AGENTOS_DEMO_MODE=off" in text
    assert "AGENTOS_AI_OFFLINE_PLACEHOLDER=off" in text
    assert "MYDOW_ROOT_REDIRECT=on" in text
    assert "--seed-demo-data" in text


def test_one_click_launchers_generate_local_only_no_mock_env() -> None:
    ps = PS_LAUNCHER.read_text(encoding="utf-8")
    sh = BASH_LAUNCHER.read_text(encoding="utf-8")
    cmd = CMD_WRAPPER.read_text(encoding="utf-8")
    wrapper = SH_WRAPPER.read_text(encoding="utf-8")

    for text in (ps, sh):
        assert ".env.docker.local" in text
        assert "AGENTOS_DEMO_MODE=off" in text
        assert "AGENTOS_AI_OFFLINE_PLACEHOLDER=off" in text
        assert "MYDOW_ROOT_REDIRECT=on" in text
        assert "LLM API URL" in text
        assert "LLM_BASE_URL" in text
        assert "DEEPSEEK_API_KEY" in text
        assert "HTTP_PORT" in text
        assert "nginx" in text
        assert "seed" in text.lower()

    assert "scripts\\run_mydow_docker.ps1" in cmd
    assert "scripts/run_mydow_docker.sh" in wrapper


def test_codex_local_run_prompt_is_copyable_and_verifiable() -> None:
    text = CODEX_PROMPT.read_text(encoding="utf-8")

    assert "docs/11-deployment/one-click-docker.md" in text
    assert "http://localhost:8080/health" in text
    assert "http://localhost:8080/ready" in text
    assert "http://localhost:8080/" in text
    assert "LLM API URL" in text
    assert "LLM API KEY" in text
    assert "不要使用 mock" in text
    assert "AGENTOS_DEMO_MODE" in text
    assert "AGENTOS_AI_OFFLINE_PLACEHOLDER" in text
