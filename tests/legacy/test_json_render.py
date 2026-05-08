"""Test suite for JSON Render Protocol."""

import pytest

from agent_os.server.json_render import (
    JSONRenderProtocol,
    create_chart,
    create_table,
    create_tree,
    render_json_text,
)


class TestJSONRenderProtocol:
    """Test suite for JSONRenderProtocol."""

    @pytest.fixture
    def protocol(self):
        """Create protocol instance."""
        return JSONRenderProtocol()

    def test_parse_empty_text(self, protocol):
        """Test parsing text with no blocks."""
        blocks = protocol.parse_render_blocks("No blocks here")
        assert blocks == []

    def test_parse_single_table_block(self, protocol):
        """Test parsing a single table block."""
        text = """
@json-render:table{title=Users}
[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
@end-json-render
"""
        blocks = protocol.parse_render_blocks(text)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "table"
        assert blocks[0]["options"]["title"] == "Users"
        assert len(blocks[0]["data"]) == 2

    def test_parse_multiple_blocks(self, protocol):
        """Test parsing multiple blocks."""
        text = """
@json-render:table{title=Data}
[{"a": 1}]
@end-json-render

@json-render:chart{type=bar}
{"a": 10, "b": 20}
@end-json-render
"""
        blocks = protocol.parse_render_blocks(text)

        assert len(blocks) == 2
        assert blocks[0]["type"] == "table"
        assert blocks[1]["type"] == "chart"

    def test_parse_block_without_options(self, protocol):
        """Test parsing block without options."""
        text = """
@json-render:json
{"key": "value"}
@end-json-render
"""
        blocks = protocol.parse_render_blocks(text)

        assert len(blocks) == 1
        assert blocks[0]["options"] == {}

    def test_parse_invalid_json_data(self, protocol):
        """Test parsing block with non-JSON data."""
        text = """
@json-render:markdown
# Heading

This is **bold** text.
@end-json-render
"""
        blocks = protocol.parse_render_blocks(text)

        assert len(blocks) == 1
        assert blocks[0]["type"] == "markdown"
        assert blocks[0]["data"] == "# Heading\n\nThis is **bold** text."

    def test_render_table_from_list_of_dicts(self, protocol):
        """Test rendering table from list of dicts."""
        data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ]

        result = protocol._render_table(data, {"title": "Users"})

        assert result["render_type"] == "table"
        assert result["title"] == "Users"
        assert result["columns"] == ["name", "age"]
        assert result["row_count"] == 2
        assert result["column_count"] == 2

    def test_render_table_from_list_of_lists(self, protocol):
        """Test rendering table from list of lists."""
        data = [
            ["Name", "Age"],
            ["Alice", 30],
            ["Bob", 25]
        ]

        result = protocol._render_table(data, {})

        assert result["columns"] == ["Name", "Age"]
        assert result["row_count"] == 2  # Excludes header row

    def test_render_table_from_dict(self, protocol):
        """Test rendering table from single dict."""
        data = {"name": "Alice", "age": 30, "city": "NYC"}

        result = protocol._render_table(data, {})

        assert result["columns"] == ["Key", "Value"]
        assert result["row_count"] == 3

    def test_render_table_from_list_of_primitives(self, protocol):
        """Test rendering table from list of primitives."""
        data = [1, 2, 3, 4, 5]

        result = protocol._render_table(data, {})

        assert result["columns"] == ["Value"]
        assert result["row_count"] == 5

    def test_render_chart_from_dict(self, protocol):
        """Test rendering chart from dict."""
        data = {"Alice": 30, "Bob": 25, "Charlie": 35}

        result = protocol._render_chart(data, {"title": "Ages"})

        assert result["render_type"] == "chart"
        assert result["title"] == "Ages"
        assert result["chart_type"] == "bar"
        assert result["point_count"] == 3
        assert result["data"][0]["x"] == "Alice"
        assert result["data"][0]["y"] == 30

    def test_render_chart_from_list_of_dicts(self, protocol):
        """Test rendering chart from list of dicts."""
        data = [
            {"x": "Jan", "y": 10},
            {"x": "Feb", "y": 20},
            {"x": "Mar", "y": 30}
        ]

        result = protocol._render_chart(data, {"type": "line"})

        assert result["chart_type"] == "line"
        assert result["point_count"] == 3

    def test_render_chart_from_list_of_pairs(self, protocol):
        """Test rendering chart from list of [x, y] pairs."""
        data = [["A", 10], ["B", 20], ["C", 30]]

        result = protocol._render_chart(data, {})

        assert result["point_count"] == 3
        assert result["data"][0]["x"] == "A"

    def test_render_tree_from_dict(self, protocol):
        """Test rendering tree from nested dict."""
        data = {
            "src": {
                "models": ["user.py", "product.py"],
                "services": "user_service.py"
            }
        }

        result = protocol._render_tree(data, {})

        assert result["render_type"] == "tree"
        assert result["node_count"] > 0
        assert result["nodes"][0]["label"] == "src"

    def test_render_tree_from_list(self, protocol):
        """Test rendering tree from list."""
        data = ["item1", "item2", "item3"]

        result = protocol._render_tree(data, {})

        assert result["node_count"] == 3
        assert all(node["leaf"] for node in result["nodes"])

    def test_render_code_with_language(self, protocol):
        """Test rendering code block."""
        data = "def hello():\n    print('world')"

        result = protocol._render_code(data, {"language": "python"})

        assert result["render_type"] == "code"
        assert result["language"] == "python"
        assert result["line_count"] == 2

    def test_render_code_from_dict(self, protocol):
        """Test rendering dict as code (JSON format)."""
        data = {"key": "value", "number": 42}

        result = protocol._render_code(data, {})

        assert result["language"] == "json"
        assert '"key"' in result["code"]
        assert '"value"' in result["code"]

    def test_render_json(self, protocol):
        """Test rendering formatted JSON."""
        data = {"users": [{"name": "Alice"}, {"name": "Bob"}]}

        result = protocol._render_json(data, {})

        assert result["render_type"] == "json"
        assert '"users"' in result["json"]
        assert '"Alice"' in result["json"]

    def test_render_list_from_list(self, protocol):
        """Test rendering list."""
        data = ["item1", "item2", "item3"]

        result = protocol._render_list(data, {"ordered": "true"})

        assert result["render_type"] == "list"
        assert result["item_count"] == 3
        assert result["ordered"] is True

    def test_render_list_from_dict(self, protocol):
        """Test rendering dict as list."""
        data = {"key1": "value1", "key2": "value2"}

        result = protocol._render_list(data, {})

        assert result["item_count"] == 2
        assert "key1: value1" in result["items"]

    def test_render_card_from_dict(self, protocol):
        """Test rendering single card."""
        data = {
            "title": "Card Title",
            "content": "Card content",
            "subtitle": "Subtitle"
        }

        result = protocol._render_card(data, {})

        assert result["render_type"] == "card"
        assert result["card_count"] == 1
        assert result["cards"][0]["title"] == "Card Title"

    def test_render_card_from_list(self, protocol):
        """Test rendering multiple cards."""
        data = [
            {"title": "Card 1", "content": "Content 1"},
            {"title": "Card 2", "content": "Content 2"}
        ]

        result = protocol._render_card(data, {})

        assert result["card_count"] == 2

    def test_render_progress_from_number(self, protocol):
        """Test rendering progress from number."""
        data = 75

        result = protocol._render_progress(data, {})

        assert result["render_type"] == "progress"
        assert result["item_count"] == 1
        assert result["items"][0]["value"] == 75
        assert result["items"][0]["percentage"] == "75%"

    def test_render_progress_from_dict(self, protocol):
        """Test rendering multiple progress bars."""
        data = {"Task 1": 30, "Task 2": 60, "Task 3": 90}

        result = protocol._render_progress(data, {})

        assert result["item_count"] == 3
        assert result["items"][0]["label"] == "Task 1"
        assert result["items"][0]["value"] == 30

    def test_render_progress_clamping(self, protocol):
        """Test that progress values are clamped to 0-100."""
        data = {"low": -10, "high": 150, "normal": 50}

        result = protocol._render_progress(data, {})

        assert result["items"][0]["value"] == 0  # Clamped from -10
        assert result["items"][1]["value"] == 100  # Clamped from 150
        assert result["items"][2]["value"] == 50

    def test_render_timeline_from_list(self, protocol):
        """Test rendering timeline from list."""
        data = [
            {"time": "2024-01-01", "title": "Event 1"},
            {"time": "2024-01-02", "title": "Event 2"}
        ]

        result = protocol._render_timeline(data, {})

        assert result["render_type"] == "timeline"
        assert result["event_count"] == 2
        assert result["events"][0]["time"] == "2024-01-01"

    def test_render_timeline_from_dict(self, protocol):
        """Test rendering timeline from dict."""
        data = {
            "2024-01-01": "First event",
            "2024-01-02": "Second event"
        }

        result = protocol._render_timeline(data, {})

        assert result["event_count"] == 2
        assert result["events"][0]["time"] == "2024-01-01"

    def test_render_fallback(self, protocol):
        """Test fallback renderer for unknown types."""
        data = {"some": "data"}

        result = protocol._render_fallback(data, {})

        assert result["render_type"] == "json"

    def test_render_all_blocks(self, protocol):
        """Test rendering all blocks in text."""
        text = """
@json-render:table{title=Table}
[{"a": 1}]
@end-json-render

@json-render:chart{type=bar}
{"x": 10}
@end-json-render
"""
        results = protocol.render_all(text)

        assert len(results) == 2
        assert results[0]["render_type"] == "table"
        assert results[1]["render_type"] == "chart"


class TestConvenienceFunctions:
    """Test suite for convenience functions."""

    def test_render_json_text(self):
        """Test render_json_text convenience function."""
        text = """
@json-render:table{title=Test}
[{"a": 1}]
@end-json-render
"""
        results = render_json_text(text)

        assert len(results) == 1
        assert results[0]["render_type"] == "table"

    def test_create_table(self):
        """Test create_table convenience function."""
        data = [{"name": "Alice", "age": 30}]
        result = create_table(data, title="Users")

        assert result["render_type"] == "table"
        assert result["title"] == "Users"

    def test_create_chart(self):
        """Test create_chart convenience function."""
        data = {"A": 10, "B": 20}
        result = create_chart(data, chart_type="pie", title="Sales")

        assert result["render_type"] == "chart"
        assert result["chart_type"] == "pie"
        assert result["title"] == "Sales"

    def test_create_tree(self):
        """Test create_tree convenience function."""
        data = {"folder": {"file1": "data1", "file2": "data2"}}
        result = create_tree(data, title="Files")

        assert result["render_type"] == "tree"
        assert result["title"] == "Files"


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_complex_table_rendering(self):
        """Test rendering a complex table with mixed data."""
        protocol = JSONRenderProtocol()

        data = [
            {"id": 1, "name": "Alice", "active": True, "score": 95.5},
            {"id": 2, "name": "Bob", "active": False, "score": 87.0},
            {"id": 3, "name": "Charlie", "active": True, "score": 92.3},
        ]

        result = protocol._render_table(data, {"title": "Students", "sortable": "true"})

        assert result["row_count"] == 3
        assert result["metadata"]["sortable"] is True

    def test_multi_chart_dashboard(self):
        """Test creating multiple charts for a dashboard."""
        protocol = JSONRenderProtocol()

        sales_data = {"Jan": 1000, "Feb": 1200, "Mar": 1500}
        user_data = {"Jan": 100, "Feb": 120, "Mar": 150}

        chart1 = protocol._render_chart(sales_data, {"type": "bar", "title": "Sales"})
        chart2 = protocol._render_chart(user_data, {"type": "line", "title": "Users"})

        assert chart1["chart_type"] == "bar"
        assert chart2["chart_type"] == "line"

    def test_file_explorer_tree(self):
        """Test rendering a file system tree."""
        protocol = JSONRenderProtocol()

        file_structure = {
            "project": {
                "src": {
                    "main.py": "code",
                    "utils.py": "code",
                },
                "tests": {
                    "test_main.py": "code",
                },
                "README.md": "doc",
            }
        }

        result = protocol._render_tree(file_structure, {"title": "Project Structure"})

        assert result["node_count"] > 5
        assert result["metadata"]["expandable"] is True

    def test_multi_step_progress(self):
        """Test rendering multi-step progress tracker."""
        protocol = JSONRenderProtocol()

        steps = {
            "Setup": 100,
            "Development": 75,
            "Testing": 50,
            "Deployment": 0
        }

        result = protocol._render_progress(steps, {"title": "Project Progress"})

        assert result["item_count"] == 4
        assert result["items"][0]["percentage"] == "100%"

    def test_project_timeline(self):
        """Test rendering project timeline."""
        protocol = JSONRenderProtocol()

        events = [
            {
                "time": "2024-01-01",
                "title": "Project Kickoff",
                "description": "Initial planning and requirements gathering",
                "icon": "🚀"
            },
            {
                "time": "2024-02-01",
                "title": "Development Start",
                "description": "Begin implementation",
                "icon": "💻"
            },
            {
                "time": "2024-03-01",
                "title": "Beta Release",
                "description": "First public beta",
                "icon": "🎉"
            }
        ]

        result = protocol._render_timeline(events, {"title": "Project Roadmap"})

        assert result["event_count"] == 3
        assert result["events"][0]["icon"] == "🚀"

    def test_mixed_content_rendering(self):
        """Test rendering mixed content (tables, charts, code)."""
        text = """
Analysis Results:

@json-render:table{title=Data Summary}
[{"metric": "Accuracy", "value": "95%"}, {"metric": "Precision", "value": "93%"}]
@end-json-render

@json-render:chart{type=bar,title=Performance}
{"Accuracy": 95, "Precision": 93, "Recall": 91}
@end-json-render

@json-render:code{language=python}
def evaluate():
    return {"accuracy": 0.95}
@end-json-render
"""
        results = render_json_text(text)

        assert len(results) == 3
        assert results[0]["render_type"] == "table"
        assert results[1]["render_type"] == "chart"
        assert results[2]["render_type"] == "code"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
