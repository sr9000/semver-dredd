"""Examples package.

The repo groups examples by language:
- `example/py` - Python examples
- `example/go` - Go examples (actual .go files)
- `example/java` - Java examples (actual .java files)

For backwards compatibility, the Python examples are re-exported so that:
- `import example.pygeometry1` works (via example/pygeometry1.py wrapper)
- `import example.pygeometry2` works (via example/pygeometry2.py wrapper)

New code may prefer `from example.py import pygeometry1`.
"""

from example.py import pygeometry1, pygeometry2

__all__ = ["pygeometry1", "pygeometry2"]
