"""Package or verify the shared EmbeddedDesigner in both IDE plugins."""

import argparse
import hashlib
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[2]
DESIGNER = ROOT.parent / "service_architect" / "service_architect_vue3"
VERSION = "0.1.12"
SOURCE = DESIGNER / "public" / "mcp-ui" / VERSION
ASSET_DIGESTS = {
    "designer.js": "1a39ed70f3b5a327a892ebb4cca87bca4141e111b6e71e3b0deea43600dbe593",
    "designer.css": "8a96a26263559c1e59472b940337b8b319710e1c0b5aa0239557044181829aae",
}
DESTINATIONS = (
    (ROOT / "service-architect-vscode", Path("media")),
    (ROOT / "service-architect-jetbrains", Path("src/main/resources/ide")),
)


def matches_release(path: Path, name: str) -> bool:
    return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == ASSET_DIGESTS[name]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify packaged assets without writing")
    parser.add_argument("--source-dir", type=Path, default=SOURCE,
                        help="built immutable Designer asset directory (default: sibling Designer checkout)")
    arguments = parser.parse_args()
    source = arguments.source_dir.resolve()
    if not arguments.check or arguments.source_dir != SOURCE:
        for name in ASSET_DIGESTS:
            if not matches_release(source / name, name):
                raise SystemExit(f"Expected immutable EmbeddedDesigner {VERSION} asset: {source / name}")
    found = 0
    for project, relative in DESTINATIONS:
        if not project.is_dir():
            continue
        found += 1
        destination = project / relative
        if not arguments.check:
            destination.mkdir(parents=True, exist_ok=True)
        for name in ASSET_DIGESTS:
            packaged = destination / name
            if arguments.check:
                if not matches_release(packaged, name):
                    raise SystemExit(f"Stale EmbeddedDesigner asset: {packaged}")
            else:
                shutil.copyfile(source / name, packaged)
    if not found:
        raise SystemExit("No sibling IDE plugin projects found in the workspace")
    if arguments.check:
        print(f"Verified EmbeddedDesigner {VERSION} in {found} IDE plugins")


if __name__ == "__main__":
    main()
