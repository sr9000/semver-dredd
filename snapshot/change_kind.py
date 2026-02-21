from enum import Enum


class ChangeKind(Enum):
    """Severity of an API change — used for semver classification.

    ========= ============================================
    Value     Meaning
    ========= ============================================
    NONE      No API surface change detected
    PATCH     Implementation-only change (no API impact)
    MINOR     New public functionality added
    BREAKING  Existing public API removed or incompatible
    ========= ============================================
    """

    NONE = 0
    PATCH = 1
    MINOR = 2
    BREAKING = 3

    @property
    def is_breaking(self) -> bool:
        return self.value == 3
