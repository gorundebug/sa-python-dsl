"""Build a local Codex plugin archive without changing its runtime pin/version."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/service-architect"

def main():
    version = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())["version"]
    destination = ROOT / "dist" / f"service-architect-codex-{version}.zip"
    destination.parent.mkdir(exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for source in sorted(PLUGIN.rglob("*")):
            if source.is_file() and "__pycache__" not in source.parts and source.suffix != ".pyc":
                archive.write(source, Path("service-architect") / source.relative_to(PLUGIN))
    print(destination)

if __name__ == "__main__":
    main()
