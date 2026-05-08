#!/usr/bin/env python3
"""
Test import fixer script.

This script identifies and fixes test import errors.
"""

from pathlib import Path

# Import mapping for incorrect imports
IMPORT_FIXES = {
    # stage4 -> search_engine
    "from agent_os.stage4.models": "from agent_os.search_engine.models",
    "from agent_os.stage4": "from agent_os.search_engine",

    # Add more mappings as needed
}


def fix_imports_in_file(file_path: Path):
    """Fix imports in a single file."""
    try:
        with open(file_path, encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Apply fixes
        for wrong_import, correct_import in IMPORT_FIXES.items():
            content = content.replace(wrong_import, correct_import)

        # Write back if changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Fix all test imports."""
    tests_dir = Path("tests")

    if not tests_dir.exists():
        print("Tests directory not found!")
        return

    # Find all Python test files
    test_files = list(tests_dir.rglob("test_*.py"))

    fixed_count = 0
    for test_file in test_files:
        if fix_imports_in_file(test_file):
            print(f"Fixed: {test_file}")
            fixed_count += 1

    print(f"\nTotal files fixed: {fixed_count}/{len(test_files)}")


if __name__ == "__main__":
    main()
