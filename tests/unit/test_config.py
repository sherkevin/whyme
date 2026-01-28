"""Tests for configuration loader."""

from pathlib import Path

import pytest
import yaml

from agent_os.core.config import Config, instantiate, load_class, load_config


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary config file for testing."""
    config_data = {
        "agent": {"name": "TestBot"},
        "memory": {
            "provider": "agent_os.memory.local_json.LocalJSONProvider",
            "config": {"storage_path": "/tmp/memory.json"},
        },
        "context": {
            "provider": "agent_os.context.sliding_window.SlidingWindowContext",
            "config": {"max_tokens": 8000},
        },
        "coding": {"provider": "agent_os.capabilities.coding.aider.AiderAdapter"},
        "sandbox": {"runtime": "docker", "image": "test:latest", "workspace": "/workspace"},
        "io": {"websocket_path": "/ws", "rest_prefix": "/api"},
    }
    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    return config_file


def test_load_config(temp_config_file: Path) -> None:
    """Test loading configuration from YAML file."""
    config = load_config(temp_config_file)

    assert isinstance(config, Config)
    assert config.agent.name == "TestBot"
    assert config.memory.provider == "agent_os.memory.local_json.LocalJSONProvider"
    assert config.memory.config["storage_path"] == "/tmp/memory.json"
    assert config.context.config["max_tokens"] == 8000
    assert config.sandbox.runtime == "docker"
    assert config.sandbox.image == "test:latest"
    assert config.io.websocket_path == "/ws"


def test_load_config_missing_file(tmp_path: Path) -> None:
    """Test loading configuration from missing file."""
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")


def test_load_class() -> None:
    """Test dynamically loading a class."""
    cls = load_class("agent_os.core.types.RuntimeContext")
    assert cls.__name__ == "RuntimeContext"


def test_instantiate() -> None:
    """Test dynamically instantiating a class."""
    obj = instantiate(
        "agent_os.core.types.RuntimeContext",
        session_id="test123",
        user_id="user1",
        trace_id="trace1",
    )
    assert obj.session_id == "test123"
    assert obj.user_id == "user1"
    assert obj.trace_id == "trace1"


def test_load_class_invalid_path() -> None:
    """Test loading a class with invalid path."""
    with pytest.raises((ImportError, AttributeError, ValueError)):
        load_class("nonexistent.module.Class")


def test_config_model_validation() -> None:
    """Test Config model validation."""
    config_data = {
        "agent": {"name": "TestBot"},
        "memory": {
            "provider": "test.Provider",
            "config": {"key": "value"},
        },
        "context": {
            "provider": "test.Context",
            "config": {"max_tokens": 5000},
        },
        "coding": {"provider": "test.Coding"},
        "sandbox": {"runtime": "docker", "image": "test:latest", "workspace": "/workspace"},
        "io": {"websocket_path": "/ws", "rest_prefix": "/api"},
    }

    config = Config(**config_data)
    assert config.agent.name == "TestBot"
    assert config.sandbox.workspace == "/workspace"
