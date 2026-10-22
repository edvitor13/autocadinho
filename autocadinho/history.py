"""Desfazer e refazer por fotografias do desenho (JSON do documento inteiro).

Desenhos de obra são pequenos: guardar o documento todo a cada mudança é simples e à prova de erro.
Mudanças seguidas com a mesma chave (digitar um nome, girar um campo numérico) viram um passo só.
"""

from __future__ import annotations

import time


class History:
    MERGE_SECONDS = 1.5

    def __init__(self, limit: int = 300) -> None:
        self.limit = limit
        self._states: list[str] = []
        self._index = -1
        self._last_key: str | None = None
        self._last_time = 0.0

    def reset(self, state: str) -> None:
        self._states = [state]
        self._index = 0
        self._last_key = None

    @property
    def current(self) -> str | None:
        return self._states[self._index] if self._states else None

    def push(self, state: str, key: str | None = None) -> bool:
        """Grava um passo. Devolve False se nada mudou."""
        if self._states and state == self._states[self._index]:
            return False
        now = time.monotonic()
        merge = (key is not None and key == self._last_key and self._index > 0
                 and self._index == len(self._states) - 1 and now - self._last_time < self.MERGE_SECONDS)
        del self._states[self._index + 1:]
        if merge:
            self._states[self._index] = state
        else:
            self._states.append(state)
            if len(self._states) > self.limit:
                del self._states[0]
            self._index = len(self._states) - 1
        self._last_key = key
        self._last_time = now
        return True

    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return self._index < len(self._states) - 1

    def undo(self) -> str | None:
        if not self.can_undo():
            return None
        self._index -= 1
        self._last_key = None
        return self._states[self._index]

    def redo(self) -> str | None:
        if not self.can_redo():
            return None
        self._index += 1
        self._last_key = None
        return self._states[self._index]
