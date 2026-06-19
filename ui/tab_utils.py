from __future__ import annotations
"""Pure-Python tab utilities — no Qt imports (importable in tests without PyQt6)."""


def tab_insert_position(panel_key: str, tab_widget, tabs_list: list) -> int:
    """Return the index at which to re-insert a panel to preserve TABS order."""
    tab_order = [k for k, _, _ in tabs_list]
    if panel_key not in tab_order:
        return tab_widget.count()
    target_pos = tab_order.index(panel_key)
    insert_at = 0
    for i in range(tab_widget.count()):
        pid = getattr(tab_widget.widget(i), "panel_id", "")
        if pid in tab_order and tab_order.index(pid) < target_pos:
            insert_at = i + 1
    return insert_at
