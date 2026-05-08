"""Enhanced RepoMap integration with Aider - Simplified robust version."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


class RepoMapEnhanced:
    """Enhanced repository map generator with code analysis.

    Features:
    - File tree structure
    - Symbol extraction (classes, functions, methods)
    - Language detection
    - Token estimation
    - Cache support
    """

    # Language-specific patterns for symbol extraction
    # Keys match the symbol types in symbols dict
    PATTERNS = {
        "python": {
            "classes": r"^\s*class\s+(\w+)",
            "functions": r"^\s*def\s+(\w+)",
            "methods": r"^\s+def\s+(\w+)",
        },
        "javascript": {
            "classes": r"class\s+(\w+)",
            "functions": r"function\s+(\w+)",
            "methods": r"^\s+(\w+)\s*\([^)]*\)\s*[{]",  # method definitions in classes
        },
        "typescript": {
            "classes": r"class\s+(\w+)",
            "functions": r"function\s+(\w+)",
            "methods": r"^\s+(\w+)\s*(?:\([^)]*\))?\s*:\s*(?:async\s+)?",
        },
        "java": {
            "classes": r"class\s+(\w+)",
            "functions": r"(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(",
        },
    }

    # Language detection by extension
    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".php": "php",
        ".rb": "ruby",
        ".kt": "kotlin",
        ".swift": "swift",
    }

    def __init__(
        self,
        root: str | None = None,
        map_tokens: int = 1024,
        verbose: bool = False,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None,
    ):
        """Initialize RepoMapEnhanced."""
        self.root = Path(root) if root else Path.cwd()
        self.map_tokens = map_tokens
        self.verbose = verbose
        self.include_patterns = include_patterns or ["**/*.py", "**/*.js", "**/*.ts", "**/*.tsx"]
        self.exclude_patterns = exclude_patterns or [
            "**/node_modules/**",
            "**/.git/**",
            "**/__pycache__/**",
            "**/venv/**",
            "**/env/**",
            "**/dist/**",
            "**/build/**",
            "**/*.egg-info/**",
        ]

    def get_repo_map(self, other_files: list[str] | None = None) -> str:
        """Generate comprehensive repository map."""
        if not self.root.exists():
            return f"# Repository Map\n\nError: Path {self.root} does not exist.\n"

        lines = []
        lines.append("# Repository Map")
        lines.append(f"Root: {self.root}")
        lines.append("")

        # Generate file tree
        lines.append("## File Structure")
        lines.append("```")
        tree = self._generate_tree()
        lines.append(tree)
        lines.append("```")
        lines.append("")

        # Generate symbol index
        lines.append("## Symbol Index")
        symbols = self._extract_symbols(other_files)
        if symbols:
            for file_path, file_symbols in symbols.items():
                rel_path = os.path.relpath(file_path, self.root)
                lines.append(f"\n### {rel_path}")

                if file_symbols.get("classes"):
                    lines.append(f"  Classes: {', '.join(file_symbols['classes'])}")
                if file_symbols.get("functions"):
                    lines.append(f"  Functions: {', '.join(file_symbols['functions'])}")
                if file_symbols.get("methods"):
                    methods = file_symbols['methods'][:10]
                    lines.append(f"  Methods: {', '.join(methods)}")
                    if len(file_symbols['methods']) > 10:
                        lines.append(f"    ... and {len(file_symbols['methods']) - 10} more")
        else:
            lines.append("No symbols found.")

        lines.append("")

        # Generate statistics
        lines.append("## Statistics")
        stats = self._get_statistics()
        lines.append(f"- Total files: {stats['total_files']}")
        lines.append(f"- Code files: {stats['code_files']}")
        lines.append(f"- Total lines: {stats['total_lines']}")
        lines.append(f"- Languages: {', '.join(stats['languages'].keys())}")
        lines.append("")

        result = "\n".join(lines)
        return result

    def _generate_tree(self, max_depth: int = 3) -> str:
        """Generate directory tree structure."""
        lines = []
        lines.append(f"{self.root.resolve()}/")
        self._add_to_tree(self.root, lines, "", 0, max_depth)
        return "\n".join(lines)

    def _add_to_tree(
        self,
        path: Path,
        lines: list[str],
        prefix: str,
        depth: int,
        max_depth: int,
        is_last: bool = False,
    ) -> None:
        """Recursively add items to tree."""
        if depth > max_depth or not path.is_dir():
            return

        # Skip excluded directories
        if self._is_excluded(path):
            return

        # Get children
        try:
            children = sorted(
                [p for p in path.iterdir() if not p.name.startswith(".")],
                key=lambda p: (not p.is_dir(), p.name),
            )
        except PermissionError:
            return

        # Filter out excluded children
        children = [c for c in children if not self._is_excluded(c)]

        # Recursively add children
        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            connector = "└── " if is_last_child else "├── "
            lines.append(f"{prefix}{connector}{child.name}/" if child.is_dir() else f"{prefix}{connector}{child.name}")

            if child.is_dir():
                new_prefix = prefix + ("    " if is_last_child else "│   ")
                self._add_to_tree(child, lines, new_prefix, depth + 1, max_depth, is_last_child)

    def _is_excluded(self, path: Path) -> bool:
        """Check if a path should be excluded."""
        path_str = str(path)

        # Check against each exclude pattern
        for pattern in self.exclude_patterns:
            # Convert glob pattern to simple check
            pattern = pattern.replace("**", "").replace("*", "")

            # Check if path contains any excluded directory
            parts = pattern.split("/")
            for part in parts:
                if part and part in path_str:
                    return True

        return False

    def _extract_symbols(self, other_files: list[str] | None = None) -> dict[str, dict[str, list[str]]]:
        """Extract symbols from code files."""
        symbols = {}
        code_files = self._get_code_files(other_files)

        for file_path in code_files:
            try:
                lang = self._detect_language(file_path)
                if lang and lang in self.PATTERNS:
                    file_symbols = self._extract_from_file(file_path, lang)
                    # Check if any symbol list is non-empty
                    has_symbols = any(len(symbols_list) > 0 for symbols_list in file_symbols.values())
                    if has_symbols:
                        symbols[str(file_path)] = file_symbols
            except Exception as e:
                if self.verbose:
                    print(f"[RepoMap] Error extracting symbols from {file_path}: {e}")

        return symbols

    def _get_code_files(self, other_files: list[str] | None = None) -> list[Path]:
        """Get all code files in the repository."""
        files = []

        # Walk directory
        for root_dir_str, dirs, filenames in os.walk(self.root):
            root_dir = Path(root_dir_str)

            # Skip hidden and excluded directories
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and not self._is_excluded(root_dir / d)
            ]

            for filename in filenames:
                file_path = root_dir / filename

                # Check if file matches include patterns
                if self._matches_include_patterns(file_path):
                    files.append(file_path)

        # Add other files
        if other_files:
            for file_path_str in other_files:
                file_path = Path(file_path_str)
                if file_path.exists() and str(file_path) not in [str(f) for f in files]:
                    files.append(file_path)

        return files

    def _matches_include_patterns(self, file_path: Path) -> bool:
        """Check if file matches include patterns."""
        for pattern in self.include_patterns:
            # Simple glob matching
            if pattern.startswith("**/"):
                # Match any directory
                if file_path.name.endswith(pattern[3:].replace("*", "")):
                    return True
            elif pattern.startswith("**"):
                # Match any path
                if file_path.suffix == pattern[2:].replace("*", ""):
                    return True
            elif "*" in pattern:
                # Simple wildcard
                suffix = pattern.replace("*", "")
                if str(file_path).endswith(suffix):
                    return True
            else:
                # Exact match
                if file_path.match(pattern):
                    return True

        return False

    def _detect_language(self, file_path: Path) -> str | None:
        """Detect programming language from file extension."""
        suffix = file_path.suffix.lower()
        return self.LANGUAGE_MAP.get(suffix)

    def _extract_from_file(self, file_path: Path, lang: str) -> dict[str, list[str]]:
        """Extract symbols from a single file."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            if self.verbose:
                print(f"[RepoMap] Error reading {file_path}: {e}")
            return {"classes": [], "functions": [], "methods": []}

        patterns = self.PATTERNS[lang]
        # Initialize all symbol types
        symbols = {
            "classes": [],
            "functions": [],
            "methods": []
        }

        for symbol_type, pattern in patterns.items():
            if pattern is None:
                continue

            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                try:
                    name = match.group(1)
                    if name and name not in symbols[symbol_type]:
                        symbols[symbol_type].append(name)
                except IndexError:
                    continue

        return symbols

    def _get_statistics(self) -> dict[str, Any]:
        """Get repository statistics."""
        stats = {
            "total_files": 0,
            "code_files": 0,
            "total_lines": 0,
            "languages": {},
        }

        code_files = self._get_code_files()
        stats["total_files"] = len(code_files)
        stats["code_files"] = len(code_files)

        for file_path in code_files:
            try:
                with open(file_path, encoding="utf-8") as f:
                    lines = len(f.readlines())
                    stats["total_lines"] += lines

                lang = self._detect_language(file_path)
                if lang:
                    stats["languages"][lang] = stats["languages"].get(lang, 0) + 1
            except Exception:
                pass

        return stats

    def get_tags_map(self, files: list[str]) -> str:
        """Generate ctags-style tags map."""
        if not files:
            return ""

        lines = []
        symbols = self._extract_symbols(files)

        for file_path, file_symbols in symbols.items():
            rel_path = os.path.relpath(file_path, self.root)

            for symbol_type in ["classes", "functions", "methods"]:
                for symbol in file_symbols.get(symbol_type, []):
                    lines.append(f"{symbol}\t{rel_path}\t/^{symbol}/")

        return "\n".join(lines)


__all__ = ["RepoMapEnhanced"]
