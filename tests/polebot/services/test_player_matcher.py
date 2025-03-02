import re

import pytest

from polebot.services.player_matcher import PlayerMatcher, PlayerProperties


def describe_validate_selector():
    def describe_valid_regex():
        def it_returns_true_and_pattern():
            ok, pattern = PlayerMatcher.validate_selector("/^test/")
            assert ok
            assert isinstance(pattern, re.Pattern)
            assert pattern.pattern == "^test"

    def describe_invalid_regex():
        def it_returns_false_and_error():
            ok, err = PlayerMatcher.validate_selector("/[invalid/")
            assert not ok
            assert err == "Selector is not a valid regular expression"

    def describe_simple_string():
        def it_returns_true_and_none():
            ok, pattern = PlayerMatcher.validate_selector("test")
            assert ok
            assert pattern is None

def describe_exact_match():
    def success():
        matcher = PlayerMatcher(selector="test_player", exact=True)
        player = PlayerProperties(name="test_player", id="1")
        assert matcher.is_match(player)


    def failure():
        matcher = PlayerMatcher(selector="test_player", exact=True)
        player = PlayerProperties(name="another_player", id="2")
        assert not matcher.is_match(player)


def describe_prefix_match():
    def success():
        matcher = PlayerMatcher(selector="test", exact=False)
        player = PlayerProperties(name="test_player", id="1")
        assert matcher.is_match(player)


    def failure():
        matcher = PlayerMatcher(selector="test", exact=False)
        player = PlayerProperties(name="another_player", id="2")
        assert not matcher.is_match(player)

def describe_regex_match():
    def name_is_match():
        matcher = PlayerMatcher(selector="/^test/", exact=False)
        player = PlayerProperties(name="test_player", id="1")
        assert matcher.is_match(player)


    def name_is_not_match():
        matcher = PlayerMatcher(selector="/^test/", exact=False)
        player = PlayerProperties(name="another_player", id="2")
        assert not matcher.is_match(player)


def describe_initialization_errors():
    def invalid_selector_raises_value_error():
        with pytest.raises(ValueError, match="Selector is not a valid regular expression"):
            PlayerMatcher(selector="/[invalid/", exact=False)


    def test_exact_match_with_pattern_raises_value_error():
        with pytest.raises(ValueError, match="Exact match requires a simple string selector"):
            PlayerMatcher(selector="/^test/", exact=True)
