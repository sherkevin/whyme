"""Runtime environment variables must win over local dotenv files."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_env_vars_are_not_overridden_by_dotenv_local() -> None:
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    env["AGENTOS_AI_LLM"] = "off"
    env["AGENTOS_DOTENV_LOCAL_OVERRIDE"] = "off"

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import os; "
                "import agent_os.core.config; "
                "print(os.environ.get('AGENTOS_AI_LLM'))"
            ),
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert proc.stdout.strip() == "off"
