# GitHub + Streamlit Community Cloud

## Repository

Push this repository to GitHub after initializing Git locally.

## App entrypoint

Use:

```text
app/streamlit_app.py
```

## Required setup

- The deployed environment must install dependencies from `pyproject.toml`.
- The app expects data through one of these paths:
  - `EBIRD_DATA_DIR`
  - `published/data`

## Recommended first public deployment

- Keep the repository code public or private depending on your GitHub and Streamlit Community Cloud access model.
- Publish only curated app-facing datasets, not the full raw local dataset.
- Prefer uploading small curated Parquet outputs into `published/data` before deploying.

## Local checklist before push

```powershell
Set-Location D:\ebird-platform
.\scripts\validate_data.ps1
.\scripts\run_app.ps1
```
