from __future__ import annotations

from ebird_platform.settings import get_app_paths


def main() -> None:
    paths = get_app_paths()
    required_dirs = [
        paths.data_dir,
        paths.analitica_dir,
        paths.dimensao_dir,
        paths.ouro_dir,
    ]

    print(f"Project root: {paths.project_root}")
    print(f"Data dir:      {paths.data_dir}")

    missing = [str(path) for path in required_dirs if not path.exists()]
    if missing:
        raise SystemExit(f"Missing required directories: {', '.join(missing)}")

    print("Data directory structure looks available.")


if __name__ == "__main__":
    main()
