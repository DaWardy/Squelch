from __future__ import annotations
# Squelch — Amateur Radio Operations Platform
# Copyright (C) 2026  github.com/dawardy/squelch
# Licensed under GNU GPL v3 — see LICENSE
"""
Squelch -- winlink/message_store.py
Winlink message inbox/outbox persistence.
Messages stored as JSON in user data directory.
"""
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from core.config import USER_DIR

log = logging.getLogger(__name__)

MSG_DIR = USER_DIR / "winlink"


@dataclass
class WinlinkMsg:
    mid:       str             # message ID
    folder:    str             # inbox / outbox / sent / drafts
    to:        str
    from_:     str
    subject:   str
    body:      str
    date_utc:  str
    status:    str = "unread"  # unread / read / sent / failed
    attachments: list = field(default_factory=list)
    via:       str = ""        # gateway used

    def to_dict(self) -> dict:
        d = asdict(self)
        d["from"] = d.pop("from_")
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "WinlinkMsg":
        d = dict(d)
        d["from_"] = d.pop("from", "")
        return cls(**d)


class MessageStore:
    def __init__(self):
        MSG_DIR.mkdir(parents=True, exist_ok=True)
        self._msgs: dict[str, WinlinkMsg] = {}
        self._load()

    def _path(self) -> Path:
        return MSG_DIR / "messages.json"

    def _load(self):
        try:
            if self._path().exists():
                data = json.loads(
                    self._path().read_text())
                for d in data:
                    m = WinlinkMsg.from_dict(d)
                    self._msgs[m.mid] = m
        except Exception as e:
            log.warning(f"Message store load: {e}")

    def save(self):
        try:
            data = [m.to_dict()
                    for m in self._msgs.values()]
            self._path().write_text(
                json.dumps(data, indent=2))
        except Exception as e:
            log.warning(f"Message store save: {e}")

    def add(self, msg: WinlinkMsg):
        self._msgs[msg.mid] = msg
        self.save()

    def get(self, mid: str) -> WinlinkMsg | None:
        return self._msgs.get(mid)

    def delete(self, mid: str):
        self._msgs.pop(mid, None)
        self.save()

    def folder(self, name: str) -> list[WinlinkMsg]:
        return [m for m in self._msgs.values()
                if m.folder == name]

    def mark_read(self, mid: str):
        if mid in self._msgs:
            self._msgs[mid].status = "read"
            self.save()

    def import_adif_message(self, path: Path) -> int:
        """Import messages from a .b2f or .adif file."""
        # Basic B2F/plaintext import
        count = 0
        try:
            content = path.read_text(
                encoding="utf-8", errors="replace")
            # Simple heuristic: split on message boundaries
            if "--- " in content or "From " in content:
                # Basic mbox-like format
                for i, block in enumerate(
                        content.split("\n\n---\n")):
                    if not block.strip():
                        continue
                    lines = block.splitlines()
                    headers = {}
                    body_lines = []
                    in_body = False
                    for line in lines:
                        if in_body:
                            body_lines.append(line)
                        elif ": " in line and not in_body:
                            k, v = line.split(": ", 1)
                            headers[k.strip()] = v.strip()
                        elif line == "":
                            in_body = True
                    msg = WinlinkMsg(
                        mid      = f"import_{int(time.time())}_{i}",
                        folder   = "inbox",
                        to       = headers.get("To", ""),
                        from_    = headers.get("From", ""),
                        subject  = headers.get("Subject", "Imported"),
                        body     = "\n".join(body_lines),
                        date_utc = headers.get("Date", ""),
                        status   = "read")
                    self.add(msg)
                    count += 1
        except Exception as e:
            log.warning(f"Import: {e}")
        return count

    @property
    def unread_count(self) -> int:
        return sum(1 for m in self._msgs.values()
                   if m.status == "unread")

    def __len__(self) -> int:
        return len(self._msgs)


# Singleton
_store: MessageStore | None = None

def get_message_store() -> MessageStore:
    global _store
    if _store is None:
        _store = MessageStore()
    return _store
