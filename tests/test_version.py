"""
Tests for Version class and version management utilities.
"""

import pytest
from datetime import date

from semverdredd import ChangeKind
from semverdredd.version import Version, generate_patch


class TestVersionParse:
    """Tests for Version.parse()."""

    def test_parse_simple_version(self):
        """Test parsing a simple version string."""
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_version_with_date_patch(self):
        """Test parsing version with YYYYMMDDZZZ patch format."""
        v = Version.parse("1.2.20260214001")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 20260214001

    def test_parse_zero_version(self):
        """Test parsing 0.0.0 version."""
        v = Version.parse("0.0.0")
        assert v.major == 0
        assert v.minor == 0
        assert v.patch == 0

    def test_parse_invalid_format_too_few_parts(self):
        """Test parsing invalid version with too few parts."""
        with pytest.raises(ValueError, match="Invalid version format"):
            Version.parse("1.2")

    def test_parse_invalid_format_too_many_parts(self):
        """Test parsing invalid version with too many parts."""
        with pytest.raises(ValueError, match="Invalid version format"):
            Version.parse("1.2.3.4")

    def test_parse_invalid_non_numeric(self):
        """Test parsing invalid version with non-numeric parts."""
        with pytest.raises(ValueError, match="Invalid version numbers"):
            Version.parse("1.2.abc")

    def test_parse_negative_version(self):
        """Test parsing negative version numbers."""
        with pytest.raises(ValueError, match="non-negative"):
            Version.parse("1.-2.3")


class TestVersionStr:
    """Tests for Version.__str__()."""

    def test_str_simple(self):
        """Test string representation of simple version."""
        v = Version(1, 2, 3)
        assert str(v) == "1.2.3"

    def test_str_with_date_patch(self):
        """Test string representation with date patch."""
        v = Version(1, 2, 20260214001)
        assert str(v) == "1.2.20260214001"

    def test_str_roundtrip(self):
        """Test parsing and converting back to string."""
        original = "1.2.20260214005"
        v = Version.parse(original)
        assert str(v) == original


class TestVersionPatchDate:
    """Tests for Version.patch_date property."""

    def test_patch_date_valid(self):
        """Test extracting date from valid patch."""
        v = Version(1, 2, 20260214001)
        assert v.patch_date == date(2026, 2, 14)

    def test_patch_date_different_date(self):
        """Test extracting different date from patch."""
        v = Version(1, 0, 20251231999)
        assert v.patch_date == date(2025, 12, 31)

    def test_patch_date_invalid_small_patch(self):
        """Test patch_date returns None for small patch numbers."""
        v = Version(1, 2, 3)
        assert v.patch_date is None

    def test_patch_date_invalid_date(self):
        """Test patch_date returns None for invalid date in patch."""
        v = Version(1, 2, 20261332001)  # Invalid month 13, day 32
        assert v.patch_date is None


class TestVersionPatchIncrement:
    """Tests for Version.patch_increment property."""

    def test_patch_increment_valid(self):
        """Test extracting increment from valid patch."""
        v = Version(1, 2, 20260214005)
        assert v.patch_increment == 5

    def test_patch_increment_small_patch(self):
        """Test increment for small patch number."""
        v = Version(1, 2, 42)
        assert v.patch_increment == 42


class TestVersionIncrement:
    """Tests for Version.increment()."""

    def test_increment_major(self):
        """Test major version increment."""
        v = Version(1, 2, 20260213001)
        new_v = v.increment(ChangeKind.BREAKING, today=date(2026, 2, 14))
        assert new_v.major == 2
        assert new_v.minor == 0
        assert new_v.patch == 20260214001

    def test_increment_minor(self):
        """Test minor version increment."""
        v = Version(1, 2, 20260213001)
        new_v = v.increment(ChangeKind.MINOR, today=date(2026, 2, 14))
        assert new_v.major == 1
        assert new_v.minor == 3
        assert new_v.patch == 20260214001

    def test_increment_patch_new_day(self):
        """Test patch version increment on new day."""
        v = Version(1, 2, 20260213001)
        new_v = v.increment(ChangeKind.PATCH, today=date(2026, 2, 14))
        assert new_v.major == 1
        assert new_v.minor == 2
        assert new_v.patch == 20260214001

    def test_increment_patch_same_day(self):
        """Test patch version increment on same day."""
        v = Version(1, 2, 20260214001)
        new_v = v.increment(ChangeKind.PATCH, today=date(2026, 2, 14))
        assert new_v.major == 1
        assert new_v.minor == 2
        assert new_v.patch == 20260214002

    def test_increment_none(self):
        """Test that NONE change type still bumps patch (any code change = new release)."""
        v = Version(1, 2, 20260214001)
        new_v = v.increment(ChangeKind.NONE, today=date(2026, 2, 14))
        # NONE triggers a patch bump since any code change warrants a new release
        assert new_v.major == 1
        assert new_v.minor == 2
        assert new_v.patch == 20260214002


class TestVersionComparison:
    """Tests for Version comparison operators."""

    def test_lt_major(self):
        """Test less than by major version."""
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)
        assert v1 < v2
        assert not v2 < v1

    def test_lt_minor(self):
        """Test less than by minor version."""
        v1 = Version(1, 2, 0)
        v2 = Version(1, 3, 0)
        assert v1 < v2

    def test_lt_patch(self):
        """Test less than by patch version."""
        v1 = Version(1, 2, 20260214001)
        v2 = Version(1, 2, 20260214002)
        assert v1 < v2

    def test_gt(self):
        """Test greater than."""
        v1 = Version(2, 0, 0)
        v2 = Version(1, 0, 0)
        assert v1 > v2

    def test_le(self):
        """Test less than or equal."""
        v1 = Version(1, 0, 0)
        v2 = Version(1, 0, 0)
        assert v1 <= v2
        v3 = Version(2, 0, 0)
        assert v1 <= v3

    def test_ge(self):
        """Test greater than or equal."""
        v1 = Version(1, 0, 0)
        v2 = Version(1, 0, 0)
        assert v1 >= v2
        v3 = Version(0, 9, 0)
        assert v1 >= v3


class TestGeneratePatch:
    """Tests for generate_patch function."""

    def test_generate_patch_first_of_day(self):
        """Test generating first patch of the day."""
        patch = generate_patch(today=date(2026, 2, 14))
        assert patch == 20260214001

    def test_generate_patch_increment_same_day(self):
        """Test incrementing patch on same day."""
        patch = generate_patch(current_patch=20260214001, today=date(2026, 2, 14))
        assert patch == 20260214002

    def test_generate_patch_new_day(self):
        """Test patch resets on new day."""
        patch = generate_patch(current_patch=20260213999, today=date(2026, 2, 14))
        assert patch == 20260214001

    def test_generate_patch_different_months(self):
        """Test patch generation across months."""
        patch = generate_patch(today=date(2026, 1, 1))
        assert patch == 20260101001

        patch = generate_patch(today=date(2026, 12, 31))
        assert patch == 20261231001

    def test_generate_patch_max_daily_releases(self):
        """Test error when exceeding max daily releases."""
        with pytest.raises(ValueError, match="Maximum daily releases"):
            generate_patch(current_patch=20260214999, today=date(2026, 2, 14))


class TestIntegerPatchScheme:
    """The "integer" scheme produces conventional incrementing patch numbers."""

    def test_default_scheme_is_date(self):
        from semverdredd.version import DEFAULT_PATCH_SCHEME, PATCH_SCHEME_DATE

        assert DEFAULT_PATCH_SCHEME == PATCH_SCHEME_DATE

    def test_generate_patch_starts_at_one(self):
        assert generate_patch(scheme="integer") == 1

    def test_generate_patch_increments(self):
        assert generate_patch(current_patch=41, scheme="integer") == 42

    def test_increment_breaking_resets_patch(self):
        v = Version(1, 2, 3).increment(ChangeKind.BREAKING, scheme="integer")
        assert (v.major, v.minor, v.patch) == (2, 0, 0)

    def test_increment_minor_resets_patch(self):
        v = Version(1, 2, 3).increment(ChangeKind.MINOR, scheme="integer")
        assert (v.major, v.minor, v.patch) == (1, 3, 0)

    def test_increment_patch(self):
        v = Version(1, 2, 3).increment(ChangeKind.PATCH, scheme="integer")
        assert (v.major, v.minor, v.patch) == (1, 2, 4)

    def test_increment_none_bumps_patch(self):
        v = Version(1, 2, 3).increment(ChangeKind.NONE, scheme="integer")
        assert (v.major, v.minor, v.patch) == (1, 2, 4)

    def test_date_scheme_explicit_matches_default(self):
        v_default = Version(1, 2, 20260213001).increment(
            ChangeKind.PATCH, today=date(2026, 2, 14)
        )
        v_explicit = Version(1, 2, 20260213001).increment(
            ChangeKind.PATCH, today=date(2026, 2, 14), scheme="date"
        )
        assert v_default == v_explicit


class TestInvalidPatchScheme:
    def test_generate_patch_rejects_unknown_scheme(self):
        with pytest.raises(ValueError, match="Unknown patch scheme"):
            generate_patch(scheme="roman-numerals")

    def test_increment_rejects_unknown_scheme(self):
        with pytest.raises(ValueError, match="Unknown patch scheme"):
            Version(1, 0, 0).increment(ChangeKind.PATCH, scheme="bogus")


class TestConfigPatchScheme:
    """versioning.patch_scheme is parsed from .semver.yaml."""

    def test_default_is_date(self, tmp_path):
        from cli.config import load_config

        config = load_config(cwd=tmp_path)
        assert config.patch_scheme == "date"

    def test_integer_from_yaml(self, tmp_path):
        from cli.config import load_config

        (tmp_path / ".semver.yaml").write_text("versioning:\n  patch_scheme: integer\n")
        config = load_config(cwd=tmp_path)
        assert config.patch_scheme == "integer"

    def test_invalid_scheme_warns_and_falls_back(self, tmp_path, capsys):
        from cli.config import load_config

        (tmp_path / ".semver.yaml").write_text("versioning:\n  patch_scheme: bogus\n")
        config = load_config(cwd=tmp_path)
        assert config.patch_scheme == "date"
        assert "patch_scheme" in capsys.readouterr().err
