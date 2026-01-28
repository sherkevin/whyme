"""Simplified RepoMap implementation for context generation."""

from __future__ import annotations

import os
from pathlib import Path


class RepoMap:
    """Generates a text representation of the repository structure."""

    def __init__(self, root: str | None = None) -> None:
        self.root = root

    def get_repo_map(self, root: str | None = None) -> str:
        """Generate a tree-like structure of the repository.
        
        Args:
            root: Root directory to map. If None, uses self.root.
            
        Returns:
            String representation of the file tree.
        """
        target_root = root or self.root
        if not target_root:
            return ""

        path = Path(target_root)
        if not path.exists():
            return f"Error: Path {target_root} does not exist."

        tree_lines = []
        
        # Walk the directory
        for root_dir, dirs, files in os.walk(target_root):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]
            
            # Calculate level
            rel_path = os.path.relpath(root_dir, target_root)
            if rel_path == ".":
                level = 0
            else:
                level = rel_path.count(os.sep) + 1
                
            indent = "  " * level
            if rel_path != ".":
                tree_lines.append(f"{indent}{os.path.basename(root_dir)}/")
            
            sub_indent = "  " * (level + 1)
            for f in files:
                tree_lines.append(f"{sub_indent}{f}")
                
        return "\n".join(tree_lines)
