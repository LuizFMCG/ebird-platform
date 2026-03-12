from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _first_existing(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    assets_dir: Path
    data_dir: Path
    analitica_dir: Path
    dimensao_dir: Path
    ouro_dir: Path
    icon_path: Path
    background_path: Path
    legacy_repo_dir: Path | None


def get_app_paths() -> AppPaths:
    project_root = _project_root()
    env_legacy = os.getenv("EBIRD_LEGACY_REPO_DIR")
    legacy_repo_dir = Path(env_legacy) if env_legacy else Path("D:/eBird")
    if not legacy_repo_dir.exists():
        legacy_repo_dir = None

    env_data = os.getenv("EBIRD_DATA_DIR")
    data_candidates = []
    if env_data:
        data_candidates.append(Path(env_data))
    data_candidates.append(project_root / "published" / "data")
    if legacy_repo_dir is not None:
        data_candidates.append(legacy_repo_dir / "Dados")
        data_candidates.append(legacy_repo_dir / "dados")
    data_dir = _first_existing(data_candidates)

    assets_dir = project_root / "assets"

    return AppPaths(
        project_root=project_root,
        assets_dir=assets_dir,
        data_dir=data_dir,
        analitica_dir=data_dir / "analitica",
        dimensao_dir=data_dir / "dimensao",
        ouro_dir=data_dir / "ouro",
        icon_path=assets_dir / "iconweb.png",
        background_path=assets_dir / "background.jpg",
        legacy_repo_dir=legacy_repo_dir,
    )
