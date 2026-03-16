from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ebird_platform.pipeline import validate
from ebird_platform.settings import AppPaths


def make_paths(root: Path) -> AppPaths:
    assets_dir = root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    icon_path = assets_dir / "iconweb.png"
    background_path = assets_dir / "background.jpg"
    icon_path.write_bytes(b"icon")
    background_path.write_bytes(b"bg")

    return AppPaths(
        project_root=root,
        assets_dir=assets_dir,
        data_dir=root / "data",
        analitica_dir=root / "data" / "analitica",
        dimensao_dir=root / "data" / "dimensao",
        ouro_dir=root / "data" / "ouro",
        icon_path=icon_path,
        background_path=background_path,
        legacy_repo_dir=None,
    )


def test_validate_main_succeeds_when_required_directories_exist(tmp_path, monkeypatch, capsys):
    paths = make_paths(tmp_path)
    paths.data_dir.mkdir()
    paths.analitica_dir.mkdir()
    paths.dimensao_dir.mkdir()

    monkeypatch.setattr(validate, "get_app_paths", lambda: paths)

    validate.main()

    out = capsys.readouterr().out
    assert "Project root" in out
    assert "Data directory structure looks available." in out


def test_validate_main_fails_when_required_directories_are_missing(tmp_path, monkeypatch):
    paths = make_paths(tmp_path)
    paths.data_dir.mkdir()

    monkeypatch.setattr(validate, "get_app_paths", lambda: paths)

    try:
        validate.main()
    except SystemExit as exc:
        assert "Missing required directories" in str(exc)
        assert str(paths.analitica_dir) in str(exc)
        assert str(paths.dimensao_dir) in str(exc)
    else:
        raise AssertionError("Expected SystemExit when directories are missing.")
