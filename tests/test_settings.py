from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ebird_platform.settings import get_app_paths


def test_paths_resolve():
    paths = get_app_paths()
    assert paths.project_root.name == "ebird-platform"
    assert paths.assets_dir.exists()
    assert paths.icon_path.exists()


def test_paths_prefer_env_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EBIRD_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("EBIRD_LEGACY_REPO_DIR", raising=False)

    paths = get_app_paths()

    assert paths.data_dir == tmp_path
