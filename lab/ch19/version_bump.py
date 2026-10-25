"""Read the version of Sift three ways and show why a bump needs a reinstall.

``importlib.metadata`` reads the ``METADATA`` file that the installer
wrote, not ``pyproject.toml``. After a bump in a temporary copy of
``pyproject.toml`` the two disagree until the package is installed
again.
"""

import re
import tomllib
from importlib.metadata import entry_points, metadata, version
from pathlib import Path

import sift

ROOT = Path(__file__).resolve().parents[2]


def bump(text: str) -> str:
    """Return pyproject text with the patch number raised by one."""
    major, minor, patch = version("sift").split(".")
    new = f'version = "{major}.{minor}.{int(patch) + 1}"'
    return re.sub(r'^version = ".*"$', new, text, count=1, flags=re.M)


def main() -> None:
    """Print the version from the metadata, the module and pyproject."""
    pyproject = ROOT / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text())["project"]["version"]
    meta = metadata("sift")
    print("importlib.metadata.version :", version("sift"))
    print("sift.__version__           :", sift.__version__)
    print("pyproject.toml             :", declared)
    print(
        "Name / Requires-Python     :", meta["Name"], meta["Requires-Python"]
    )
    print("Requires-Dist              :")
    for requirement in meta.get_all("Requires-Dist") or []:
        print("  ", requirement)
    scripts = entry_points(group="console_scripts")
    print("console script             :", scripts["sift"].value)
    bumped = tomllib.loads(bump(pyproject.read_text()))["project"]["version"]
    print()
    print(f"after a bump in a temp copy: pyproject says {bumped},")
    print(f"importlib.metadata still says {version('sift')}")
    print("(pip install -e . / uv sync rewrites the METADATA)")


if __name__ == "__main__":
    main()
