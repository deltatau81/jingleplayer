"""Pure pool selection. Commit runtime state only after a successful start."""

from copy import deepcopy
from pathlib import Path, PureWindowsPath
import random


def pool_file_path(raw, base):
    """Join local relative paths to an explicit base, without filesystem/CWD lookup."""
    path = Path(raw)
    if path.is_absolute():
        return path
    if PureWindowsPath(raw).anchor or path.root:
        raise ValueError("Absoluter fremder oder laufwerksrelativer Pfad ist hier nicht erreichbar.")
    base = Path(base)
    if not base.is_absolute():
        raise ValueError("Kein expliziter absoluter Settings-Basisordner vorhanden.")
    return base / path


def validate_pool(value):
    """Return a detached configuration; files are checked only when playing.

    selected_audio is a stable, unchanged path, not a positional index. Duplicate
    spellings are rejected without guessing host-specific filesystem identities.
    """
    if type(value) is not dict or set(value) != {"audio_pool", "audio_pool_mode", "selected_audio"}:
        raise ValueError("Ein Pool braucht Dateiliste, Modus und manuelle Auswahl.")
    paths = value["audio_pool"]
    if type(paths) is not list or not paths:
        raise ValueError("Ein aktiver Pool darf nicht leer sein; bitte Einzeldatei verwenden.")
    for path in paths:
        if (type(path) is not str or not path or
                any(c == "\0" or 0xD800 <= ord(c) <= 0xDFFF for c in path)):
            raise ValueError("Ungültiger Audiopfad im Pool.")
        if PureWindowsPath(path).suffix.lower() not in (".mp3", ".wav"):
            raise ValueError("Pools unterstützen nur MP3 und WAV.")
    if len(set(paths)) != len(paths):
        raise ValueError("Doppelte Pfade im Pool sind nicht erlaubt.")
    if type(value["audio_pool_mode"]) is not str or value["audio_pool_mode"] not in ("sequential", "random", "manual"):
        raise ValueError("Ungültiger Poolmodus.")
    if type(value["selected_audio"]) is not str or value["selected_audio"] not in paths:
        raise ValueError("Die manuelle Auswahl muss im Pool enthalten sein.")
    return deepcopy(value)


class PoolSelector:
    """Runtime-only states keyed by preset/slot; configuration edits reset state."""

    def __init__(self, chooser=None):
        self.states = {}
        self.chooser = chooser

    def reset(self):
        self.states.clear()

    def _state(self, key, pool):
        signature = (tuple(pool["audio_pool"]), pool["audio_pool_mode"])
        state = self.states.get(key)
        if state is None or state["signature"] != signature:
            state = {"signature": signature, "next": 0, "last": None}
            self.states[key] = state
        return state

    def candidates(self, key, pool):
        state = self._state(key, pool)
        paths = pool["audio_pool"]
        mode = pool["audio_pool_mode"]
        if mode == "manual":
            return [pool["selected_audio"]]
        if mode == "sequential":
            start = state["next"]
            return paths[start:] + paths[:start]
        remaining = [p for p in paths if p != state["last"]]
        ordered = []
        if self.chooser is None:
            random.shuffle(remaining)
            ordered = remaining
        else:
            while remaining:
                path = self.chooser(remaining)
                remaining.remove(path)
                ordered.append(path)
        # Retry the last successful file only if every alternative is unusable.
        if state["last"] in paths:
            ordered.append(state["last"])
        return ordered

    def started(self, key, pool, path):
        state = self._state(key, pool)
        state["next"] = (pool["audio_pool"].index(path) + 1) % len(pool["audio_pool"])
        state["last"] = path
