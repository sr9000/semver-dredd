# semver-dredd

Automatically increments semver number based on interface changes.

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
poetry install
```
