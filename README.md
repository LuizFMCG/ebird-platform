# eBird Platform

Parallel repository for the eBird analytics project. This codebase preserves the current analytical behavior while organizing the app, configuration, dataset contracts, and AWS publication workflow.

## Local run

```powershell
Set-Location D:\ebird-platform
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m streamlit run .\app\streamlit_app.py
```

By default, the app resolves data from these candidates, in order:

1. `EBIRD_DATA_DIR`
2. `D:\ebird-platform\published\data`
3. `D:\eBird\Dados`
4. `D:\eBird\dados`

## Validation

```powershell
.\.venv\Scripts\python.exe -m ebird_platform.pipeline.validate
pytest
```

## Operational scripts

```powershell
.\scripts\validate_data.ps1
.\scripts\run_app.ps1
```

## Publishing

- Streamlit Community Cloud deployment notes: `docs/deploy_streamlit_cloud.md`
- AWS bootstrap commands: `docs/aws_bootstrap.md`
- Current-state technical analysis and next-phase recommendation: `docs/current_state_analysis.md`
