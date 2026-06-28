"""Optional Icarus markdown-memory provenance for Daedalus.

Daedalus should not fail a paid job because memory is unavailable. This wrapper
keeps all writes best-effort and returns explicit status.
"""

import contextlib
import io
import json
import sys

from . import config


class MemoryRecorder:
    def __init__(self, enabled=None, root=None, agent="hermes"):
        self.setting = config.DAEDALUS_MEMORY_ENABLED if enabled is None else enabled
        self.root = root or config.DAEDALUS_MEMORY_ROOT
        self.agent = agent
        self._mem = None
        self._error = ""
        if str(self.setting).lower() in {"0", "false", "no", "off", "disabled"}:
            self._error = "disabled"
            return
        try:
            IcarusMemory = self._load_icarus()

            self._mem = IcarusMemory(root=self.root, platform="hermes")
        except Exception as e:
            self._error = str(e)
            if str(self.setting).lower() in {"1", "true", "yes", "on", "enabled"}:
                # Explicitly enabled still stays non-fatal, but surfaces why it failed.
                self._error = f"enabled but unavailable: {e}"

    @property
    def available(self):
        return self._mem is not None

    def _load_icarus(self):
        try:
            from icarus_memory import IcarusMemory

            return IcarusMemory
        except ModuleNotFoundError:
            sibling = config.ROOT.parent / "icarus-memory" / "src"
            if sibling.exists():
                sys.path.insert(0, str(sibling))
                from icarus_memory import IcarusMemory

                return IcarusMemory
            raise

    def status(self):
        if self.available:
            return {"enabled": True, "root": self.root, "status": "ready"}
        return {"enabled": False, "root": self.root, "status": self._error or "unavailable"}

    def record(self, *, kind, summary, body="", source_tool="daedalus", order_id="", evidence=None):
        if not self.available:
            return {"enabled": False, "error": self._error or "icarus-memory unavailable"}
        try:
            writer = self._mem.advanced.write if hasattr(self._mem, "advanced") else self._mem.write
            entry = writer(
                agent=self.agent,
                type=kind,
                summary=summary,
                body=body if isinstance(body, str) else json.dumps(body, indent=2, default=str),
                platform="hermes",
                project_id=config.PROJECT_NAME,
                session_id=order_id or None,
                source_tool=source_tool,
                evidence=evidence or [],
            )
            return {"enabled": True, "id": entry.id, "root": self.root}
        except Exception as e:
            return {"enabled": False, "error": str(e)}

    def recall(self, query, k=5):
        """Recall this agent's own business memory (daedalus project) to inform
        decisions across sessions. Returns ranked past entries."""
        if not self.available:
            return {"enabled": False, "error": self._error or "icarus-memory unavailable", "hits": []}
        try:
            # the fabric may hold malformed legacy entries; silence their skip-warnings
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                hits = self._mem.recall(query, k=k, project_id=config.PROJECT_NAME)
            out = []
            for h in hits:
                e = getattr(h, "entry", h)
                out.append({"id": getattr(e, "id", ""), "type": getattr(e, "type", ""),
                            "summary": getattr(e, "summary", ""), "ts": str(getattr(e, "timestamp", ""))})
            return {"enabled": True, "count": len(out), "hits": out}
        except Exception as e:
            return {"enabled": False, "error": str(e), "hits": []}
