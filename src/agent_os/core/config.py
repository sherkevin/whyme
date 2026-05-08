"""Configuration loader for dynamic class loading from YAML config."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables from .env first, then allow local developer
# overrides from .env.local. The latter is gitignored and may contain secrets.
load_dotenv()
load_dotenv(".env.local", override=True)


class AgentConfig(BaseModel):
    """Agent configuration."""

    name: str


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: str
    config: dict[str, Any]

    def get_api_key(self) -> str | None:
        """Get API key from environment or config."""
        return (
            os.getenv("API_KEY")
            or os.getenv("LITELLM_API_KEY")
            or os.getenv("DEEPSEEK_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or self.config.get("api_key")
        )

    def get_api_base(self) -> str | None:
        """Get API base URL from environment or config."""
        return (
            os.getenv("BASE_URL")
            or os.getenv("API_BASE")
            or os.getenv("DEEPSEEK_OPENAI_BASE_URL")
            or self.config.get("api_base")
        )


class MemoryConfig(BaseModel):
    """Memory provider configuration."""

    provider: str
    config: dict[str, Any]


class ContextConfig(BaseModel):
    """Context manager configuration."""

    provider: str
    config: dict[str, Any]


class CodingConfig(BaseModel):
    """Coding capability configuration."""

    provider: str


class SandboxConfig(BaseModel):
    """Sandbox configuration."""

    runtime: str
    image: str
    workspace: str


class IOConfig(BaseModel):
    """IO configuration."""

    websocket_path: str
    rest_prefix: str


class Config(BaseModel):
    """Root configuration model."""

    agent: AgentConfig
    llm: LLMConfig | None = None
    memory: MemoryConfig
    context: ContextConfig
    coding: CodingConfig | None = None
    sandbox: SandboxConfig | None = None
    io: IOConfig | None = None


def load_config(path: str | Path) -> Config:
    """Load configuration from YAML file."""
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path_obj, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Config(**data)


def load_class(class_path: str) -> type:
    """Dynamically load a class from its dotted path.

    Args:
        class_path: Dotted path like "package.module.ClassName"

    Returns:
        The loaded class
    """
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def instantiate(class_path: str, *args: Any, **kwargs: Any) -> Any:
    """Instantiate a class from its dotted path.

    Args:
        class_path: Dotted path like "package.module.ClassName"
        *args: Positional arguments to pass to the class constructor
        **kwargs: Keyword arguments to pass to the class constructor

    Returns:
        An instance of the class
    """
    cls = load_class(class_path)
    return cls(*args, **kwargs)


# ============================================================================
# Garden Configuration
# ============================================================================

def get_garden_strong_edge_threshold() -> float:
    """Get the strong edge threshold for Garden knowledge graph.

    Reads from environment variable GARDEN_STRONG_EDGE_THRESHOLD.
    Returns default value 0.65 if not set.

    Returns:
        float: Strong edge threshold (0.0 - 1.0)
    """
    threshold = os.getenv("GARDEN_STRONG_EDGE_THRESHOLD")
    if threshold is None:
        return 0.65

    try:
        value = float(threshold)
        # Clamp to valid range [0.0, 1.0]
        return max(0.0, min(1.0, value))
    except (ValueError, TypeError):
        return 0.65


def get_garden_config() -> dict[str, Any]:
    """Get all Garden-related configuration.

    Returns:
        dict: Garden configuration including:
            - strong_edge_threshold: Threshold for strong edges (default: 0.65)
    """
    return {
        "strong_edge_threshold": get_garden_strong_edge_threshold(),
    }
