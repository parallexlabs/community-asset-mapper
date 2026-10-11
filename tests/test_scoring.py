"""Jaro-Winkler scoring edge cases."""

from community_asset_mapper.dedup.scoring import jaro_winkler


def test_jaro_winkler_similar() -> None:
    score = jaro_winkler("martha", "marhta")
    assert 0.9 < score < 1.0


def test_jaro_winkler_prefix_bonus() -> None:
    score = jaro_winkler("prefix_a", "prefix_b")
    assert score > jaro_winkler("aaaa_a", "bbbb_b")
