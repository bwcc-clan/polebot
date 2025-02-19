import pytest

from polebot.services.settings_loader import SettingsLoader


def describe_load_weighting_parameters():
    @pytest.fixture
    def sut() -> SettingsLoader:
        return SettingsLoader()

    def when_valid_json_file():

        def returns_weighting_parameters(sut):
            sut = SettingsLoader()
            content = """{
                "groups": {
                    "group1": {
                        "weight": 80,
                        "repeat_decay": 0.5,
                        "maps": ["map1", "map2"]
                    }
                },
                "environments": {
                    "env1": {
                        "weight": 50,
                        "repeat_decay": 0.5,
                        "environments": ["day", "dusk"]
                    }
                }
            }"""
            result = sut.load_weighting_parameters(content)
            assert not isinstance(result, list)
            assert result.groups["group1"].weight == 80
            assert result.groups["group1"].repeat_decay == 0.5
            assert result.groups["group1"].maps == ["map1", "map2"]
            assert result.environments["env1"].weight == 50
            assert result.environments["env1"].repeat_decay == 0.5
            assert result.environments["env1"].environments == ["day", "dusk"]

    def when_json_contains_schema_ref():

        def returns_weighting_parameters(sut):
            sut = SettingsLoader()
            content = """{
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "https://example.com/weighting_parameters.schema.json",
                "groups": {
                    "group1": {
                        "weight": 80,
                        "repeat_decay": 0.5,
                        "maps": ["map1", "map2"]
                    }
                },
                "environments": {
                    "env1": {
                        "weight": 50,
                        "repeat_decay": 0.5,
                        "environments": ["day", "dusk"]
                    }
                }
            }"""
            result = sut.load_weighting_parameters(content)
            assert not isinstance(result, list)
            assert result.groups["group1"].weight == 80
            assert result.groups["group1"].repeat_decay == 0.5
            assert result.groups["group1"].maps == ["map1", "map2"]
            assert result.environments["env1"].weight == 50
            assert result.environments["env1"].repeat_decay == 0.5
            assert result.environments["env1"].environments == ["day", "dusk"]
    def when_json_file_is_invalid():

        def detects_missing_groups(sut: SettingsLoader):
            sut = SettingsLoader()
            content = """{
                "environments": {
                    "env1": {
                        "weight": 50,
                        "repeat_decay": 0.5,
                        "environments": ["day", "dusk"]
                    }
                }
            }"""
            result = sut.load_weighting_parameters(content)
            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0].message == "'groups' is a required property"
            assert result[0].json_path == "$"
