
import json
from pathlib import Path

from jsonschema import Draft202012Validator, ValidationError

from polebot.models import WeightingParameters
from polebot.services import cattrs_helpers


class SettingsLoader:
    def __init__(self) -> None:
        schema_path = Path(__file__).parent.resolve().joinpath("weighting_parameters.schema.json")
        self._schema = json.loads(schema_path.read_text())
        self._validator = Draft202012Validator(self._schema)
        self._converter = cattrs_helpers.make_params_converter()

    def load_weighting_parameters(self, content: str) -> list[ValidationError] | WeightingParameters:
        json_content = json.loads(content)
        errors: list[ValidationError] = sorted(self._validator.iter_errors(instance=json_content), key=lambda e: e.path)
        if errors:
            return errors

        return self._converter.structure(json_content, WeightingParameters)
