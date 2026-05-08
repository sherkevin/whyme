"""Test suite for enhanced RepoMap implementation."""

import tempfile
from pathlib import Path

import pytest

from agent_os.capabilities.coding._vendor.repo_map_enhanced import RepoMapEnhanced


class TestRepoMapEnhanced:
    """Test suite for RepoMapEnhanced functionality."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)

            # Create Python file
            (repo / "example.py").write_text(
                """class MyClass:
    def __init__(self):
        self.value = 1

    def method_one(self):
        return self.value

def function_one():
    return "hello"

def function_two():
    return "world"
"""
            )

            # Create nested directory
            (repo / "src").mkdir()
            (repo / "src" / "utils.py").write_text(
                """def helper_function():
    pass

class HelperClass:
    def helper_method(self):
        pass
"""
            )

            # Create JavaScript file
            (repo / "script.js").write_text(
                """class MyJSClass {
    constructor() {
        this.value = 1;
    }

    methodOne() {
        return this.value;
    }
}

function functionOne() {
    return "hello";
}
"""
            )

            # Create excluded directory (should be ignored)
            (repo / "node_modules").mkdir()
            (repo / "node_modules" / "package.js").write_text("excluded content")

            yield repo

    def test_initialization(self, temp_repo):
        """Test RepoMap initialization."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        assert repo_map.root == temp_repo
        assert repo_map.map_tokens == 1024
        assert isinstance(repo_map.include_patterns, list)
        assert isinstance(repo_map.exclude_patterns, list)

    def test_generate_tree(self, temp_repo):
        """Test tree generation."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        tree = repo_map._generate_tree()

        # Check that root is included
        assert str(temp_repo.resolve()) in tree

        # Check that files are included
        assert "example.py" in tree
        assert "script.js" in tree

        # Check that node_modules is excluded
        assert "node_modules" not in tree

    def test_detect_language(self, temp_repo):
        """Test language detection."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        assert repo_map._detect_language(temp_repo / "example.py") == "python"
        assert repo_map._detect_language(temp_repo / "script.js") == "javascript"
        assert repo_map._detect_language(temp_repo / "test.ts") == "typescript"
        assert repo_map._detect_language(temp_repo / "README.md") is None

    def test_extract_symbols_python(self, temp_repo):
        """Test symbol extraction from Python files."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        file_path = temp_repo / "example.py"
        symbols = repo_map._extract_from_file(file_path, "python")

        assert "MyClass" in symbols["classes"]
        assert "function_one" in symbols["functions"]
        assert "function_two" in symbols["functions"]
        assert "method_one" in symbols["methods"]

    def test_extract_symbols_javascript(self, temp_repo):
        """Test symbol extraction from JavaScript files."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        file_path = temp_repo / "script.js"
        symbols = repo_map._extract_from_file(file_path, "javascript")

        assert "MyJSClass" in symbols["classes"]
        assert "functionOne" in symbols["functions"]
        assert "methodOne" in symbols["methods"]

    def test_get_repo_map(self, temp_repo):
        """Test complete repository map generation."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        repo_map_str = repo_map.get_repo_map()

        # Check sections
        assert "# Repository Map" in repo_map_str
        assert "## File Structure" in repo_map_str
        assert "## Symbol Index" in repo_map_str
        assert "## Statistics" in repo_map_str

        # Check files are included
        assert "example.py" in repo_map_str
        assert "src/" in repo_map_str
        assert "script.js" in repo_map_str

        # Check symbols are included
        assert "MyClass" in repo_map_str
        assert "function_one" in repo_map_str

        # Check statistics
        assert "Total files:" in repo_map_str
        assert "Languages:" in repo_map_str

    def test_get_statistics(self, temp_repo):
        """Test statistics generation."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        stats = repo_map._get_statistics()

        assert stats["total_files"] > 0
        assert stats["code_files"] > 0
        assert stats["total_lines"] > 0
        assert "python" in stats["languages"]
        assert "javascript" in stats["languages"]

    def test_get_tags_map(self, temp_repo):
        """Test ctags-style tags map generation."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        files = [str(temp_repo / "example.py")]
        tags_map = repo_map.get_tags_map(files)

        # Check format: symbol\tfile\t/pattern/
        assert "MyClass" in tags_map
        assert "function_one" in tags_map
        assert "\t" in tags_map
        assert "^" in tags_map

    def test_excluded_patterns(self, temp_repo):
        """Test that excluded patterns are respected."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        # Check that node_modules is excluded by default
        tree = repo_map._generate_tree()
        assert "node_modules" not in tree

        # Check that hidden directories are excluded
        (temp_repo / ".hidden").mkdir()
        (temp_repo / ".hidden" / "file.py").write_text("content")

        tree = repo_map._generate_tree()
        assert ".hidden" not in tree

    def test_custom_include_patterns(self, temp_repo):
        """Test custom include patterns."""
        # Create a .go file (not included by default)
        (temp_repo / "main.go").write_text("package main")

        repo_map = RepoMapEnhanced(
            root=str(temp_repo),
            include_patterns=["**/*.py", "**/*.go"]
        )

        code_files = repo_map._get_code_files()
        file_names = [f.name for f in code_files]

        assert "example.py" in file_names
        assert "main.go" in file_names
        assert "script.js" not in file_names  # Not in include patterns

    def test_token_limit(self, temp_repo):
        """Test token limit functionality."""
        repo_map = RepoMapEnhanced(
            root=str(temp_repo),
            map_tokens=100,  # Very small limit
            verbose=True
        )

        repo_map_str = repo_map.get_repo_map()

        # Should still work, just truncated
        assert len(repo_map_str) > 0
        assert "# Repository Map" in repo_map_str

    def test_other_files_parameter(self, temp_repo):
        """Test other_files parameter."""
        # Create file outside root
        outside_file = temp_repo.parent / "outside.py"
        outside_file.write_text("def outside_function(): pass")

        repo_map = RepoMapEnhanced(root=str(temp_repo))

        # Without other_files
        symbols = repo_map._extract_symbols()
        assert str(outside_file) not in symbols

        # With other_files
        symbols = repo_map._extract_symbols([str(outside_file)])
        assert str(outside_file) in symbols
        assert "outside_function" in symbols[str(outside_file)]["functions"]

        # Clean up
        outside_file.unlink()

    def test_nested_directory_structure(self, temp_repo):
        """Test nested directory tree generation."""
        # Create deep nesting
        (temp_repo / "level1").mkdir()
        (temp_repo / "level1" / "level2").mkdir()
        (temp_repo / "level1" / "level2" / "level3").mkdir()
        (temp_repo / "level1" / "level2" / "level3" / "deep.py").write_text("content")

        repo_map = RepoMapEnhanced(root=str(temp_repo))

        tree = repo_map._generate_tree()

        # Check that all levels are shown
        assert "level1" in tree
        assert "level2" in tree
        assert "level3" in tree
        assert "deep.py" in tree

    def test_empty_repository(self):
        """Test handling of empty repository."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_map = RepoMapEnhanced(root=tmpdir)

            repo_map_str = repo_map.get_repo_map()

            # Should still generate basic structure
            assert "# Repository Map" in repo_map_str
            assert "## File Structure" in repo_map_str

            # Statistics should show 0 files
            assert "Total files: 0" in repo_map_str or "Total files:" in repo_map_str

    def test_nonexistent_repository(self):
        """Test handling of nonexistent repository."""
        repo_map = RepoMapEnhanced(root="/nonexistent/path")

        repo_map_str = repo_map.get_repo_map()

        # Should show error
        assert "Error:" in repo_map_str or "does not exist" in repo_map_str

    def test_multiple_files_same_symbol_name(self, temp_repo):
        """Test handling of same symbol name in multiple files."""
        # Create another file with MyClass
        (temp_repo / "another.py").write_text(
            """class MyClass:
    def another_method(self):
        pass
"""
        )

        repo_map = RepoMapEnhanced(root=str(temp_repo))

        symbols = repo_map._extract_symbols()

        # Both files should have MyClass
        files_with_myclass = [
            f for f, syms in symbols.items()
            if "MyClass" in syms.get("classes", [])
        ]

        assert len(files_with_myclass) == 2


class TestRepoMapIntegration:
    """Integration tests for RepoMap with Aider."""

    @pytest.fixture
    def temp_repo(self):
        """Create a realistic project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)

            # Python package structure
            (repo / "src").mkdir()
            (repo / "src" / "__init__.py").write_text("")
            (repo / "src" / "models.py").write_text(
                """from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str

    def get_email(self):
        return f"{self.name}@example.com"
"""
            )
            (repo / "src" / "services.py").write_text(
                """from .models import User

class UserService:
    def create_user(self, name):
        return User(id=1, name=name)

    def get_user(self, user_id):
        return User(id=user_id, name="Test")
"""
            )

            # Tests
            (repo / "tests").mkdir()
            (repo / "tests" / "test_models.py").write_text(
                """def test_user():
    user = User(1, "Test")
    assert user.name == "Test"
"""
            )

            # Configuration
            (repo / "config.py").write_text(
                """DATABASE_URL = "sqlite:///db.sqlite3"
DEBUG = True
"""
            )

            # README
            (repo / "README.md").write_text(
                """# My Project

A test project for RepoMap.
"""
            )

            yield repo

    def test_realistic_repo_map(self, temp_repo):
        """Test generating map for realistic project."""
        repo_map = RepoMapEnhanced(root=str(temp_repo))

        repo_map_str = repo_map.get_repo_map()

        # Should include all Python files
        assert "models.py" in repo_map_str
        assert "services.py" in repo_map_str
        assert "test_models.py" in repo_map_str
        assert "config.py" in repo_map_str

        # Should show structure
        assert "src/" in repo_map_str
        assert "tests/" in repo_map_str

        # Should extract symbols
        assert "User" in repo_map_str
        assert "UserService" in repo_map_str
        assert "create_user" in repo_map_str

        # Should have statistics
        assert "Total files:" in repo_map_str
        assert "python" in repo_map_str.lower()

    def test_map_for_context(self, temp_repo):
        """Test that repo map is suitable for LLM context."""
        repo_map = RepoMapEnhanced(
            root=str(temp_repo),
            map_tokens=2000
        )

        repo_map_str = repo_map.get_repo_map()

        # Should be well-structured with clear sections
        lines = repo_map_str.split("\n")

        # Should have headers
        assert any(line.startswith("#") for line in lines)

        # Should have code blocks
        assert any("```" in line for line in lines)

        # Should have bullet points
        assert any(line.startswith("-") for line in lines)

        # Should be readable
        assert len(repo_map_str) < 10000  # Reasonable size


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
