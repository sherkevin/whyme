#!/usr/bin/env python3
"""§16.9 — Static audit: `data-toast` labels in biz_v14 vs bridge wiring.

Reads `static/mydow/biz_v14/index.html` and cross-checks:
  - `bridge_v14_ext.js` — `buildDataToastHandlers` string keys (`"…": async`).
  - `bridge_v14.js` — handler map keys, `data-toast="…"` selectors, `intentMap` entries,
    and a few special cases (`data-notice-quick`, `dataset.toast`).

Writes JSON to `.tmp/v14_button_audit.json`. Does not start a browser.

Usage::
    python scripts/audit_v14_buttons.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "static/mydow/biz_v14/index.html"
BRIDGE_PATH = ROOT / "static/mydow/biz_v14/bridge_v14.js"
EXT_PATH = ROOT / "static/mydow/biz_v14/bridge_v14_ext.js"
OUT_PATH = ROOT / ".tmp/v14_button_audit.json"


def _extract_html_data_toast_counts(html: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for m in re.finditer(r'data-toast="([^"]+)"', html):
        t = m.group(1)
        counts[t] = counts.get(t, 0) + 1
    return counts


def _extract_ext_handler_keys(ext_js: str) -> set[str]:
    start = ext_js.find("function buildDataToastHandlers")
    if start < 0:
        return set()
    sub = ext_js[start:]
    end = sub.find("function bindDataToastIntercept")
    if end > 0:
        sub = sub[:end]
    return set(re.findall(r'"([^"]+)"\s*:\s*async', sub))


def _extract_bridge_intent_map_keys(bridge_js: str) -> set[str]:
    keys: set[str] = set()
    for m in re.finditer(
        r"intentMap\s*=\s*\{([^}]*)\}",
        bridge_js,
        re.DOTALL,
    ):
        inner = m.group(1)
        keys.update(re.findall(r'"([^"]+)"\s*:\s*"[^"]+"', inner))
    return keys


def _extract_bridge_async_keys(bridge_js: str) -> set[str]:
    return set(re.findall(r'"([^"]+)"\s*:\s*async', bridge_js))


def _bridge_selector_hits(bridge_js: str, label: str) -> list[str]:
    reasons: list[str] = []
    if f'data-toast="{label}"' in bridge_js:
        reasons.append("literal_attr")
    sel = f'[data-toast="{label}"]'
    if sel in bridge_js:
        reasons.append("css_selector")
    if f'dataset.toast !== "{label}"' in bridge_js or f'dataset.toast === "{label}"' in bridge_js:
        reasons.append("dataset_guard")
    return reasons


def _special_html_labels() -> dict[str, str]:
    """Labels tied to non-standard attributes in HTML; bridge may wire differently."""
    return {
        "已全部标记为已读": "data-notice-quick=markRead in bridge + toast text",
    }


# Primary `<button data-toast="…">` inside `.surface-layer[data-modal]` whose click is
# dispatched by `bindModalSubmitsCapture` → `MODAL_SUBMIT_HANDLERS[modalName]` (bridge_v14.js).
# Built from `static/mydow/biz_v14/index.html` modal foot actions.
MODAL_PRIMARY_TOAST_TO_MODAL: dict[str, str] = {
    "上传任务已创建": "uploadFile",
    "网页已保存到最近捕捉": "webLink",
    "深度研究任务已创建": "deepResearch",
    "知识库文件夹已创建": "newFolder",
}


def _extract_modal_submit_modal_names(bridge_js: str) -> set[str]:
    m = re.search(
        r"const MODAL_SUBMIT_HANDLERS = \{([\s\S]*?)\n  \};",
        bridge_js,
    )
    if not m:
        return set()
    inner = m.group(1)
    return set(re.findall(r"\b([a-zA-Z][a-zA-Z0-9_]*)\s*:\s*handle", inner))


def _extract_pref_toggle_labels(bridge_js: str) -> set[str]:
    idx = bridge_js.find("function bindPrefToggleV39")
    if idx < 0:
        return set()
    chunk = bridge_js[idx : idx + 1200]
    m = re.search(r"const map = \{([^}]+)\}", chunk, re.DOTALL)
    if not m:
        return set()
    return set(re.findall(r'"([^"]+)"\s*:\s*"[a-z_]+"', m.group(1)))


def _verify_modal_map_against_html(html: str) -> None:
    for label, modal in MODAL_PRIMARY_TOAST_TO_MODAL.items():
        if f'data-modal="{modal}"' not in html:
            raise RuntimeError(f"audit map: missing data-modal={modal} in index.html")
        if f'data-toast="{label}"' not in html:
            raise RuntimeError(f"audit map: missing data-toast={label} in index.html")


def main() -> int:
    html = HTML_PATH.read_text(encoding="utf-8")
    bridge_js = BRIDGE_PATH.read_text(encoding="utf-8")
    ext_js = EXT_PATH.read_text(encoding="utf-8")

    _verify_modal_map_against_html(html)

    html_counts = _extract_html_data_toast_counts(html)
    ext_keys = _extract_ext_handler_keys(ext_js)
    bridge_async = _extract_bridge_async_keys(bridge_js)
    intent_keys = _extract_bridge_intent_map_keys(bridge_js)
    modal_submit_modals = _extract_modal_submit_modal_names(bridge_js)
    pref_toggle_labels = _extract_pref_toggle_labels(bridge_js)

    rows: list[dict] = []
    missing: list[str] = []

    for label in sorted(html_counts.keys()):
        in_ext = label in ext_keys
        in_bridge_maps = label in bridge_async or label in intent_keys
        selector_hits = _bridge_selector_hits(bridge_js, label)
        special = _special_html_labels().get(label)
        modal_for_label = MODAL_PRIMARY_TOAST_TO_MODAL.get(label)
        via_modal = bool(
            modal_for_label and modal_for_label in modal_submit_modals
        )
        via_pref_map = label in pref_toggle_labels

        covered = bool(
            in_ext
            or in_bridge_maps
            or selector_hits
            or special
            or via_modal
            or via_pref_map
        )

        if not covered:
            missing.append(label)

        rows.append(
            {
                "label": label,
                "html_occurrences": html_counts[label],
                "covered": covered,
                "via_ext_buildDataToastHandlers": in_ext,
                "via_bridge_async_handler_key": label in bridge_async,
                "via_bridge_intent_map": label in intent_keys,
                "via_bridge_selector_or_guard": selector_hits,
                "via_bridge_modal_submit": {
                    "data_modal": modal_for_label,
                    "handler_registered": via_modal,
                },
                "via_bridge_pref_toggle_map": via_pref_map,
                "special_note": special,
            },
        )

    payload = {
        "generated_by": "scripts/audit_v14_buttons.py",
        "html_path": str(HTML_PATH.relative_to(ROOT)),
        "bridge_path": str(BRIDGE_PATH.relative_to(ROOT)),
        "ext_path": str(EXT_PATH.relative_to(ROOT)),
        "summary": {
            "unique_labels_in_html": len(html_counts),
            "total_data_toast_attrs_in_html": sum(html_counts.values()),
            "ext_handler_keys": len(ext_keys),
            "bridge_async_keys": len(bridge_async),
            "intent_map_keys": len(intent_keys),
            "modal_submit_modal_names": sorted(modal_submit_modals),
            "pref_toggle_labels": sorted(pref_toggle_labels),
            "labels_with_no_static_wiring": missing,
        },
        "rows": rows,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    if missing:
        print("\nWARN: labels with no static wiring match:", ", ".join(missing))
        return 1
    print("\nOK: every HTML data-toast label has a static bridge reference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
