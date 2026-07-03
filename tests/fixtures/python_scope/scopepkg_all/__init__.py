"""Fixture package for Python plugin scope tests (with __all__)."""

__all__ = ["visible_func"]


def visible_func() -> None:
    pass


def invisible_func() -> None:
    """Not in __all__, must never appear in the snapshot even though public."""
    pass
