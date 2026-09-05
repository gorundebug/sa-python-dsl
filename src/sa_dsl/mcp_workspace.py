from __future__ import annotations

from pathlib import Path


class WorkspaceBoundaryError(ValueError):
    pass


class WorkspaceBoundary:
    def __init__(self, root: str | Path) -> None:
        candidate = Path(root).expanduser()
        if not candidate.is_dir():
            raise WorkspaceBoundaryError(f"workspace root is not a directory: {candidate}")
        self.root = candidate.resolve(strict=True)

    def resolve(self, relative: str | Path = ".") -> Path:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise WorkspaceBoundaryError(
                "path must be relative to the registered MCP workspace"
            )
        resolved = (self.root / candidate).resolve(strict=False)
        if resolved != self.root and self.root not in resolved.parents:
            raise WorkspaceBoundaryError(
                "path resolves outside the registered MCP workspace"
            )
        return resolved
