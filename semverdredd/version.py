"""
Version management for semver-dredd.

Handles semantic versioning with two patch schemes:

- "date" (default): YYYYMMDDZZZ — date-encoded patch with a daily counter
- "integer": conventional incrementing patch numbers (0, 1, 2, ...)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

# from typing import Self  # Removed to support Python 3.10 without typing_extensions

PATCH_SCHEME_DATE = "date"
PATCH_SCHEME_INTEGER = "integer"
PATCH_SCHEMES = (PATCH_SCHEME_DATE, PATCH_SCHEME_INTEGER)
DEFAULT_PATCH_SCHEME = PATCH_SCHEME_DATE


@dataclass
class Version:
    """
    Represents a semantic version with custom patch format.

    Patch format: YYYYMMDDZZZ
    - YYYY: Year
    - MM: Month (01-12)
    - DD: Day (01-31)
    - ZZZ: Daily increment (001-999)
    """

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, version_str: str) -> Version:
        """
        Parse a version string into a Version object.

        Args:
            version_str: Version string like "1.2.20260214001"

        Returns:
            Version object

        Raises:
            ValueError: If version string is invalid
        """
        parts = version_str.strip().split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid version format: {version_str}. Expected 'major.minor.patch'"
            )

        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
        except ValueError as e:
            raise ValueError(f"Invalid version numbers in: {version_str}") from e

        if major < 0 or minor < 0 or patch < 0:
            raise ValueError(f"Version numbers must be non-negative: {version_str}")

        return cls(major=major, minor=minor, patch=patch)

    def __str__(self) -> str:
        """Return version as string 'major.minor.patch'."""
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def patch_date(self) -> date | None:
        """Extract date from patch version, or None if invalid format."""
        if self.patch < 100000000:  # Not in YYYYMMDDZZZ format
            return None
        patch_str = str(self.patch)
        if len(patch_str) < 11:
            return None
        try:
            year = int(patch_str[:4])
            month = int(patch_str[4:6])
            day = int(patch_str[6:8])
            return date(year, month, day)
        except ValueError:
            return None

    @property
    def patch_increment(self) -> int:
        """Extract daily increment (ZZZ) from patch version."""
        if self.patch < 100000000:
            return self.patch
        patch_str = str(self.patch)
        if len(patch_str) < 11:
            return 0
        return int(patch_str[8:])

    def increment(
        self,
        change_type,
        today: date | None = None,
        scheme: str = DEFAULT_PATCH_SCHEME,
    ) -> Version:
        """
        Increment version based on change type.

        Args:
            change_type: Type of API change detected (ChangeKind enum or compatible)
            today: Date to use for patch version (defaults to today; "date"
                scheme only)
            scheme: Patch scheme — "date" (YYYYMMDDZZZ, default) or "integer"
                (conventional incrementing patch, reset to 0 on major/minor)

        Returns:
            New Version object with incremented version
        """
        _validate_scheme(scheme)

        if today is None:
            today = date.today()

        # Use name comparison to avoid circular import issues
        change_name = (
            change_type.name if hasattr(change_type, "name") else str(change_type)
        )

        if change_name == "BREAKING":
            # Major bump: increment major, reset minor, new patch
            if scheme == PATCH_SCHEME_INTEGER:
                return Version(major=self.major + 1, minor=0, patch=0)
            return Version(
                major=self.major + 1, minor=0, patch=generate_patch(today=today)
            )
        elif change_name == "MINOR":
            # Minor bump: increment minor, new patch
            if scheme == PATCH_SCHEME_INTEGER:
                return Version(major=self.major, minor=self.minor + 1, patch=0)
            return Version(
                major=self.major,
                minor=self.minor + 1,
                patch=generate_patch(today=today),
            )
        else:
            # PATCH or NONE: new patch version (any code change = new release)
            if scheme == PATCH_SCHEME_INTEGER:
                return Version(
                    major=self.major,
                    minor=self.minor,
                    patch=generate_patch(
                        current_patch=self.patch, scheme=PATCH_SCHEME_INTEGER
                    ),
                )
            current_patch = self.patch if self.patch_date == today else None
            return Version(
                major=self.major,
                minor=self.minor,
                patch=generate_patch(current_patch=current_patch, today=today),
            )

    def __lt__(self, other: Version) -> bool:
        """Compare versions for sorting."""
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (
            other.major,
            other.minor,
            other.patch,
        )

    def __le__(self, other: Version) -> bool:
        return self == other or self < other

    def __gt__(self, other: Version) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self.major, self.minor, self.patch) > (
            other.major,
            other.minor,
            other.patch,
        )

    def __ge__(self, other: Version) -> bool:
        return self == other or self > other


def _validate_scheme(scheme: str) -> None:
    if scheme not in PATCH_SCHEMES:
        raise ValueError(
            f"Unknown patch scheme: {scheme!r}. Valid schemes: {', '.join(PATCH_SCHEMES)}"
        )


def generate_patch(
    current_patch: int | None = None,
    today: date | None = None,
    scheme: str = DEFAULT_PATCH_SCHEME,
) -> int:
    """
    Generate a new patch version number.

    Args:
        current_patch: Current patch version to increment
        today: Date to use (defaults to today; "date" scheme only)
        scheme: Patch scheme — "date" (YYYYMMDDZZZ, default) or "integer"
            (conventional incrementing patch numbers)

    Returns:
        New patch version number
    """
    _validate_scheme(scheme)

    if scheme == PATCH_SCHEME_INTEGER:
        return (current_patch or 0) + 1

    if today is None:
        today = date.today()

    date_prefix = int(f"{today.year:04d}{today.month:02d}{today.day:02d}")
    base_patch = date_prefix * 1000  # YYYYMMDD000

    if current_patch is None:
        return base_patch + 1  # First release of the day: YYYYMMDD001

    # Check if current patch is from the same day
    current_date_prefix = current_patch // 1000
    if current_date_prefix == date_prefix:
        # Same day, increment ZZZ
        current_increment = current_patch % 1000
        new_increment = current_increment + 1
        if new_increment > 999:
            raise ValueError(f"Maximum daily releases (999) exceeded for {today}")
        return base_patch + new_increment
    else:
        # Different day, start fresh
        return base_patch + 1


def save_version_file(version: str, path: Path | str = "VERSION") -> None:
    """Save version string to a plain text file."""
    path = Path(path)
    path.write_text(f"{version}\n")


def load_version_file(path: Path | str = "VERSION") -> str:
    """Load version string from a plain text file."""
    path = Path(path)
    return path.read_text().strip()
