from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ebird_platform.io import loaders


def test_load_diversidade_estado_uses_latest_run_and_normalizes_columns(tmp_path, monkeypatch):
    old_run = tmp_path / "diversidade_estado_latam_appstyle__run_20250101_000000.parquet"
    new_run = tmp_path / "diversidade_estado_latam_appstyle__run_20260101_000000.parquet"
    old_run.touch()
    new_run.touch()
    os.utime(old_run, (1, 1))
    os.utime(new_run, (2, 2))

    monkeypatch.setattr(loaders, "ANALITICA_DIR", tmp_path)

    def fake_read_parquet(path: Path) -> pd.DataFrame:
        assert path == new_run
        return pd.DataFrame(
            {
                "pais_iso3_x": ["BRA", "BRA"],
                "id_estado": [35, 35],
                "n_registros": [10, 20],
                "richness": [5, 7],
            }
        )

    monkeypatch.setattr(loaders.pd, "read_parquet", fake_read_parquet)

    result = loaders.load_diversidade_estado_conesul_appstyle()

    assert list(result.columns) == [
        "pais_iso3",
        "id_estado",
        "n_registros_total",
        "n_especies_distintas_max_municipio",
        "id_municipio_max",
    ]
    row = result.iloc[0]
    assert len(result) == 1
    assert row["pais_iso3"] == "BRA"
    assert row["id_estado"] == 35
    assert row["n_registros_total"] == 10
    assert row["n_especies_distintas_max_municipio"] == 5
    assert pd.isna(row["id_municipio_max"])


def test_load_cubo_normalizes_alternative_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(loaders, "ANALITICA_DIR", tmp_path)

    monkeypatch.setattr(
        loaders.pd,
        "read_parquet",
        lambda path: pd.DataFrame(
            {
                "countryCode": ["BR"],
                "stateProvince": ["SP"],
                "county": ["Sao Paulo"],
                "taxon_name": ["Turdus leucomelas"],
                "count": [3],
            }
        ),
    )

    result = loaders.load_cubo_cidade_especie_total()

    assert list(result.columns) == [
        "countryCode",
        "stateProvince",
        "county",
        "scientificName",
        "n_registros",
    ]
    assert result.iloc[0].to_dict() == {
        "countryCode": "BR",
        "stateProvince": "SP",
        "county": "Sao Paulo",
        "scientificName": "Turdus leucomelas",
        "n_registros": 3,
    }


def test_load_cubo_raises_when_required_columns_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(loaders, "ANALITICA_DIR", tmp_path)
    monkeypatch.setattr(loaders.pd, "read_parquet", lambda path: pd.DataFrame({"countryCode": ["BR"]}))

    try:
        loaders.load_cubo_cidade_especie_total()
    except ValueError as exc:
        assert "faltando colunas" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing cube columns.")
