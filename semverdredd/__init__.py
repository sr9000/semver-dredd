"""
Automatically increments semver number based on interface changes.

semver consists of three numbers: major, minor, and patch.

Major version is incremented when there are breaking changes to the public API.
Minor version is incremented when there are new features added to the public API, but no breaking changes.
Patch version is equal YYYYMMDDZZZ.
- YYYY is the current year.
- MM is the current month.
- DD is the current day.
- ZZZ is a zero-padded incremental number that starts at 001 for each day and increments with each patch release on the same day.
"""
