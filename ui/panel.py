"""SquelchPanel base class for all dockable panels."""
from __future__ import annotations
from typing import Any


class SquelchPanel:
    """Mixin base class. Use alongside QWidget:
        class MyTab(SquelchPanel, QWidget): ...
    """
    panel_id:    str = ""
    panel_title: str = ""

    def save_state(self) -> dict[str, Any]:
        """Return JSON-serialisable panel state. Override per-panel."""
        return {}

    def restore_state(self, state: dict[str, Any]) -> None:
        """Apply previously-saved state. Override per-panel."""

    def panel_actions(self) -> list:
        """QActions for the panel title-bar context menu. Override."""
        return []
