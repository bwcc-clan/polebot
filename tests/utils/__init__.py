
from pathlib import Path


def support_files_dir(file: str) -> Path:
    f = Path(file)
    dir = f.parent.resolve().joinpath(f.stem)
    return dir
