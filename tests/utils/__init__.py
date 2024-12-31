
from pathlib import Path
from unittest.mock import AsyncMock

type JSON = dict[str, "JSON"] | list["JSON"] | str | int | float | bool | None

def support_files_dir(file: str) -> Path:
    f = Path(file)
    path = f.parent.resolve().joinpath(f.stem)
    return path

def create_mock_json_response(expected_response: JSON) -> AsyncMock:
    mock_response = AsyncMock()
    mock_response.__aenter__.return_value = mock_response
    mock_response.__aexit__.return_value = None
    mock_response.json = AsyncMock(return_value=expected_response)
    return mock_response
