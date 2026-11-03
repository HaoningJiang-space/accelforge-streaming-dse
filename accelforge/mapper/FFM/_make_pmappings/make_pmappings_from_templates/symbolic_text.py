"""Render immutable formula diagnostics once per template, including its targets."""
from functools import lru_cache


class SymbolicText:
    def __init__(self):
        # Instance-local caches are released after the template. Mutable Goal
        # objects are deliberately not cached: their current state must be logged.
        self._str = lru_cache(maxsize=512, typed=True)(str)
        self._repr = lru_cache(maxsize=512, typed=True)(repr)

    def __call__(self, expression):
        return self._str(expression)

    def goals(self, goals):
        return '{' + ', '.join(f'{self._repr(f)}: {g!r}' for f, g in goals.items()) + '}'
