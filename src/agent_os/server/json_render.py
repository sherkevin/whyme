"""JSON Render Protocol for Rich Media Visualization.

This module implements the @json-render protocol for displaying
structured data in various visual formats (tables, charts, trees, etc.).
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List


class RenderType(str, Enum):
    """Supported render types."""

    TABLE = "table"
    CHART = "chart"
    TREE = "tree"
    CODE = "code"
    JSON = "json"
    MARKDOWN = "markdown"
    LIST = "list"
    CARD = "card"
    PROGRESS = "progress"
    TIMELINE = "timeline"


class ChartType(str, Enum):
    """Supported chart types."""

    BAR = "bar"
    LINE = "line"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"


class JSONRenderProtocol:
    """Handler for @json-render protocol.

    The @json-render protocol allows LLMs to request structured data
    visualization by embedding special markup in their responses.

    Format: @json-render:type{options}
            data
            @end-json-render
    """

    def __init__(self):
        """Initialize JSON Render Protocol handler."""
        self.renderers = {
            RenderType.TABLE: self._render_table,
            RenderType.CHART: self._render_chart,
            RenderType.TREE: self._render_tree,
            RenderType.CODE: self._render_code,
            RenderType.JSON: self._render_json,
            RenderType.MARKDOWN: self._render_markdown,
            RenderType.LIST: self._render_list,
            RenderType.CARD: self._render_card,
            RenderType.PROGRESS: self._render_progress,
            RenderType.TIMELINE: self._render_timeline,
        }

    def parse_render_blocks(self, text: str) -> list[dict[str, Any]]:
        """Parse @json-render blocks from text.

        Args:
            text: Text containing @json-render blocks

        Returns:
            List of parsed render blocks with metadata
        """
        import re

        blocks = []
        pattern = r"@json-render:(\w+)(?:\{(.*?)\})?\s*\n(.*?)\n@end-json-render"

        for match in re.finditer(pattern, text, re.DOTALL):
            render_type = match.group(1)
            options_str = match.group(2) or ""
            data_str = match.group(3)

            try:
                # Parse options
                options = {}
                if options_str.strip():
                    # Simple key=value parsing
                    for opt in options_str.split(","):
                        if "=" in opt:
                            key, value = opt.split("=", 1)
                            options[key.strip()] = value.strip()

                # Parse data (try JSON first, then raw text)
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = data_str

                blocks.append({
                    "type": render_type,
                    "options": options,
                    "data": data,
                    "raw": match.group(0)
                })
            except Exception:
                # Invalid block, skip it
                continue

        return blocks

    def render_block(self, block: dict[str, Any]) -> dict[str, Any]:
        """Render a single block.

        Args:
            block: Parsed block dictionary

        Returns:
            Rendered output with metadata
        """
        render_type = block.get("type", "json")
        data = block.get("data")
        options = block.get("options", {})

        try:
            render_type_enum = RenderType(render_type)
            renderer = self.renderers.get(render_type_enum)

            if renderer:
                return renderer(data, options)
            else:
                return self._render_fallback(data, options)
        except ValueError:
            # Unknown render type, use fallback
            return self._render_fallback(data, options)

    def render_all(self, text: str) -> list[dict[str, Any]]:
        """Render all @json-render blocks in text.

        Args:
            text: Text containing @json-render blocks

        Returns:
            List of rendered outputs
        """
        blocks = self.parse_render_blocks(text)
        return [self.render_block(block) for block in blocks]

    def _render_table(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as table.

        Args:
            data: Tabular data (list of dicts or list of lists)
            options: Render options (title, columns, etc.)

        Returns:
            Table render output
        """
        # Default options
        title = options.get("title", "Table")

        # Normalize data to list of dicts
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                # List of dicts - use keys as columns
                columns = list(data[0].keys())
                rows = [[str(row.get(col, "")) for col in columns] for row in data]
            elif data and isinstance(data[0], (list, tuple)):
                # List of lists - first row is header
                columns = list(data[0])
                rows = [list(row) for row in data[1:]]
            else:
                # List of primitives
                columns = ["Value"]
                rows = [[str(item)] for item in data]
        elif isinstance(data, dict):
            # Single dict - render as key-value pairs
            columns = ["Key", "Value"]
            rows = [[k, str(v)] for k, v in data.items()]
        else:
            # Fallback
            columns = ["Data"]
            rows = [[str(data)]]

        return {
            "render_type": "table",
            "title": title,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(columns),
            "metadata": {
                "sortable": options.get("sortable", "true") == "true",
                "filterable": options.get("filterable", "true") == "true",
            }
        }

    def _render_chart(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as chart.

        Args:
            data: Chart data
            options: Chart options (type, title, axes, etc.)

        Returns:
            Chart render output
        """
        chart_type = options.get("type", "bar")
        title = options.get("title", "Chart")
        x_axis = options.get("x_axis", "x")
        y_axis = options.get("y_axis", "y")

        # Normalize data
        if isinstance(data, dict):
            # Dict to points
            points = [{"x": k, "y": v} for k, v in data.items()]
        elif isinstance(data, list):
            if data and isinstance(data[0], dict):
                # List of dicts
                points = data
            elif data and isinstance(data[0], (list, tuple)) and len(data[0]) >= 2:
                # List of [x, y] pairs
                points = [{"x": item[0], "y": item[1]} for item in data]
            else:
                # List of values
                points = [{"x": i, "y": item} for i, item in enumerate(data)]
        else:
            points = []

        return {
            "render_type": "chart",
            "chart_type": chart_type,
            "title": title,
            "x_axis": x_axis,
            "y_axis": y_axis,
            "data": points,
            "point_count": len(points),
            "metadata": {
                "interactive": options.get("interactive", "true") == "true",
                "legend": options.get("legend", "true") == "true",
            }
        }

    def _render_tree(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as tree structure.

        Args:
            data: Tree data (nested dict/list)
            options: Tree options

        Returns:
            Tree render output
        """
        title = options.get("title", "Tree")

        def build_tree(obj, depth=0):
            """Recursively build tree structure."""
            if isinstance(obj, dict):
                return [
                    {
                        "label": str(k),
                        "children": build_tree(v, depth + 1),
                        "depth": depth,
                        "expanded": depth < 2  # Auto-expand first 2 levels
                    }
                    for k, v in obj.items()
                ]
            elif isinstance(obj, list):
                return [
                    {
                        "label": str(item),
                        "children": [],
                        "depth": depth,
                        "leaf": True
                    }
                    for item in obj
                ]
            else:
                return [
                    {
                        "label": str(obj),
                        "children": [],
                        "depth": depth,
                        "leaf": True
                    }
                ]

        tree_nodes = build_tree(data)

        return {
            "render_type": "tree",
            "title": title,
            "nodes": tree_nodes,
            "node_count": self._count_nodes(tree_nodes),
            "metadata": {
                "expandable": options.get("expandable", "true") == "true",
                "selectable": options.get("selectable", "true") == "true",
            }
        }

    def _count_nodes(self, nodes: list[dict]) -> int:
        """Count total nodes in tree."""
        count = 0
        for node in nodes:
            count += 1
            if node.get("children"):
                count += self._count_nodes(node["children"])
        return count

    def _render_code(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as code block.

        Args:
            data: Code string or structured code data
            options: Code options (language, theme, etc.)

        Returns:
            Code render output
        """
        language = options.get("language", "python")
        title = options.get("title", f"Code ({language})")
        line_numbers = options.get("line_numbers", "true") == "true"

        # Convert data to string
        if isinstance(data, dict):
            # Pretty print JSON
            code = json.dumps(data, indent=2)
            language = "json"
        elif isinstance(data, (list, tuple)):
            code = "\n".join(str(item) for item in data)
        else:
            code = str(data)

        lines = code.split("\n")

        return {
            "render_type": "code",
            "title": title,
            "language": language,
            "code": code,
            "line_count": len(lines),
            "line_numbers": line_numbers,
            "metadata": {
                "copyable": options.get("copyable", "true") == "true",
                "theme": options.get("theme", "default"),
            }
        }

    def _render_json(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as formatted JSON.

        Args:
            data: Any JSON-serializable data
            options: JSON options (indent, theme, etc.)

        Returns:
            JSON render output
        """
        title = options.get("title", "JSON Data")
        indent = int(options.get("indent", "2"))

        # Format JSON
        json_str = json.dumps(data, indent=indent, ensure_ascii=False)

        return {
            "render_type": "json",
            "title": title,
            "json": json_str,
            "metadata": {
                "copyable": options.get("copyable", "true") == "true",
                "collapsed": options.get("collapsed", "false") == "true",
            }
        }

    def _render_markdown(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as markdown.

        Args:
            data: Markdown string
            options: Markdown options

        Returns:
            Markdown render output
        """
        title = options.get("title", "Markdown")
        markdown = str(data)

        return {
            "render_type": "markdown",
            "title": title,
            "content": markdown,
            "metadata": {
                "sanitize": options.get("sanitize", "true") == "true",
            }
        }

    def _render_list(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as list.

        Args:
            data: List data
            options: List options (ordered, icons, etc.)

        Returns:
            List render output
        """
        title = options.get("title", "List")
        ordered = options.get("ordered", "false") == "true"

        # Normalize to list
        if isinstance(data, list):
            items = [str(item) for item in data]
        elif isinstance(data, dict):
            items = [f"{k}: {v}" for k, v in data.items()]
        else:
            items = [str(data)]

        return {
            "render_type": "list",
            "title": title,
            "items": items,
            "item_count": len(items),
            "ordered": ordered,
            "metadata": {
                "icons": options.get("icons", "false") == "true",
            }
        }

    def _render_card(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as card(s).

        Args:
            data: Card data (dict for single card, list for multiple)
            options: Card options

        Returns:
            Card render output
        """
        title = options.get("title", "")

        # Normalize to list of cards
        if isinstance(data, list):
            cards = data
        elif isinstance(data, dict):
            cards = [data]
        else:
            cards = [{"content": str(data)}]

        # Ensure each card has required fields
        normalized_cards = []
        for card in cards:
            if isinstance(card, dict):
                normalized_cards.append({
                    "title": card.get("title", ""),
                    "content": str(card.get("content", card)),
                    "subtitle": card.get("subtitle", ""),
                    "footer": card.get("footer", ""),
                    "image": card.get("image", ""),
                })
            else:
                normalized_cards.append({
                    "title": "",
                    "content": str(card),
                    "subtitle": "",
                    "footer": "",
                    "image": "",
                })

        return {
            "render_type": "card",
            "title": title,
            "cards": normalized_cards,
            "card_count": len(normalized_cards),
            "metadata": {
                "clickable": options.get("clickable", "false") == "true",
            }
        }

    def _render_progress(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as progress indicator(s).

        Args:
            data: Progress data (number for single, list/dict for multiple)
            options: Progress options

        Returns:
            Progress render output
        """
        title = options.get("title", "Progress")

        # Normalize to list of progress items
        if isinstance(data, (int, float)):
            items = [{"value": data, "label": ""}]
        elif isinstance(data, list):
            items = [
                {"value": item, "label": ""}
                if isinstance(item, (int, float))
                else item
                for item in data
            ]
        elif isinstance(data, dict):
            items = [
                {"value": v, "label": k}
                for k, v in data.items()
            ]
        else:
            items = [{"value": 0, "label": ""}]

        # Normalize values to 0-100 range
        for item in items:
            value = item.get("value", 0)
            if isinstance(value, (int, float)):
                item["value"] = max(0, min(100, value))
                item["percentage"] = f"{item['value']}%"

        return {
            "render_type": "progress",
            "title": title,
            "items": items,
            "item_count": len(items),
            "metadata": {
                "animated": options.get("animated", "true") == "true",
                "show_label": options.get("show_label", "true") == "true",
            }
        }

    def _render_timeline(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Render data as timeline.

        Args:
            data: Timeline data (list of events)
            options: Timeline options

        Returns:
            Timeline render output
        """
        title = options.get("title", "Timeline")

        # Normalize to list of events
        if isinstance(data, list):
            events = data
        elif isinstance(data, dict):
            events = [
                {"time": k, "title": str(v)}
                for k, v in data.items()
            ]
        else:
            events = []

        # Ensure each event has required fields
        normalized_events = []
        for event in events:
            if isinstance(event, dict):
                normalized_events.append({
                    "time": str(event.get("time", "")),
                    "title": str(event.get("title", "")),
                    "description": str(event.get("description", event.get("content", ""))),
                    "icon": event.get("icon", ""),
                })
            elif isinstance(event, str):
                normalized_events.append({
                    "time": "",
                    "title": event,
                    "description": "",
                    "icon": "",
                })

        return {
            "render_type": "timeline",
            "title": title,
            "events": normalized_events,
            "event_count": len(normalized_events),
            "metadata": {
                "order": options.get("order", "chronological"),
            }
        }

    def _render_fallback(self, data: Any, options: dict[str, Any]) -> dict[str, Any]:
        """Fallback renderer for unknown types.

        Args:
            data: Any data
            options: Options (ignored)

        Returns:
            JSON render output
        """
        return self._render_json(data, options)


# Convenience functions

def render_json_text(text: str) -> list[dict[str, Any]]:
    """Render all @json-render blocks in text.

    Args:
        text: Text containing @json-render blocks

    Returns:
        List of rendered outputs

    Example:
        >>> text = '''
        ... @json-render:table{title=Users}
        ... [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        ... @end-json-render
        ... '''
        >>> renders = render_json_text(text)
        >>> renders[0]['render_type']
        'table'
    """
    protocol = JSONRenderProtocol()
    return protocol.render_all(text)


def create_table(data: Any, title: str = "Table", **options) -> dict[str, Any]:
    """Create a table render.

    Args:
        data: Tabular data
        title: Table title
        **options: Additional options

    Returns:
        Table render output
    """
    protocol = JSONRenderProtocol()
    return protocol._render_table(data, {"title": title, **options})


def create_chart(data: Any, chart_type: str = "bar", title: str = "Chart", **options) -> dict[str, Any]:
    """Create a chart render.

    Args:
        data: Chart data
        chart_type: Type of chart (bar, line, pie, etc.)
        title: Chart title
        **options: Additional options

    Returns:
        Chart render output
    """
    protocol = JSONRenderProtocol()
    return protocol._render_chart(data, {"type": chart_type, "title": title, **options})


def create_tree(data: Any, title: str = "Tree", **options) -> dict[str, Any]:
    """Create a tree render.

    Args:
        data: Tree data
        title: Tree title
        **options: Additional options

    Returns:
        Tree render output
    """
    protocol = JSONRenderProtocol()
    return protocol._render_tree(data, {"title": title, **options})


__all__ = [
    "JSONRenderProtocol",
    "RenderType",
    "ChartType",
    "render_json_text",
    "create_table",
    "create_chart",
    "create_tree",
]
