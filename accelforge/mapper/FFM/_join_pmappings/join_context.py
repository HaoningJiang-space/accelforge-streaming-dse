"""Strict context binding for resumable reference-order FFM composition."""
from copy import deepcopy
from dataclasses import dataclass, field
import os
from uuid import uuid4


def _switches():
    return tuple(sorted((k, v) for k, v in os.environ.items() if k.startswith('AF_')))


@dataclass(frozen=True)
class JoinContext:
    """A captured Spec and search contract, with identity-based reuse only.

    No semantic equality across Specs or continuation graphs is inferred.
    Private state is owned by this context; callers receive copies via spec_copy.
    """
    _spec: object = field(repr=False, compare=False)
    token: str = field(default_factory=lambda: uuid4().hex)
    switches: tuple = field(default_factory=_switches)
    skip_invalid: bool = True
    combine_reservations: bool = True
    lookahead_filter: bool = True
    row_filter: object = field(default=None, repr=False, compare=False)
    terminal_observer: object = field(default=None, repr=False, compare=False)

    @classmethod
    def from_spec(cls, spec, **kwargs):
        return cls(deepcopy(spec), **kwargs)

    def spec_copy(self):
        return deepcopy(self._spec)

    def __deepcopy__(self, memo):
        # A context is an identity-bound contract, not per-transition state.
        # Preserve callback identity and share the privately captured read-only Spec.
        return self

    def check_environment(self):
        if self.switches != _switches():
            raise ValueError('FFM search switches changed since JoinContext creation')

    def require_same(self, other):
        self.check_environment()
        if other is not self:
            raise ValueError('partial Join state belongs to a different context')
