# semver-dredd

Automatically increments semver number based on interface changes.

## Features

- Detects breaking changes (removed functions/classes, added required parameters)
- Detects minor changes (new functions/classes, new optional parameters)
- Compares module APIs by introspecting Python modules
- Supports class and function signature analysis

## Installation

```bash
poetry install
```

## Usage

```python
from semverdredd import detect_change, ChangeType
from example import pygeometry1, pygeometry2

change = detect_change(pygeometry1, pygeometry2)
if change == ChangeType.MAJOR:
    print("Breaking change detected!")
elif change == ChangeType.MINOR:
    print("New features added.")
else:
    print("No API changes.")
```

## Versioning Scheme

`semver-dredd` uses a specific versioning strategy:
- **Major**: Incremented when there are breaking changes to the public API.
- **Minor**: Incremented when there are new features added to the public API, but no breaking changes.
- **Patch**: Follows the format `YYYYMMDDZZZ`.
  - `YYYY`: Current year.
  - `MM`: Current month.
  - `DD`: Current day.
  - `ZZZ`: A zero-padded incremental number that starts at 001 for each day and increments with each patch release on the same day.

## Development

This project uses Poetry for dependency management.

```bash
poetry install --with dev
```

## Running Tests

```bash
poetry run pytest -v
```

## License

MIT
