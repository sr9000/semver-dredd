"""Examples package.

The repo groups examples by language (`example/py`, `example/go`, `example/java`).

For backwards compatibility, the Python examples are re-exported so that:
- `import example.pygeometry1` works
- `import example.pygeometry2` works

New code may prefer `from example.py import pygeometry1`.
"""

from example.py import pygeometry1, pygeometry2

__all__ = ["pygeometry1", "pygeometry2"]
