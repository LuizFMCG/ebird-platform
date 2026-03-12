# Architecture

## Principles

- Preserve current analytical behavior first.
- Externalize heavy data from the repository.
- Treat map gradients and analytical aggregations as business logic.
- Keep the Streamlit app as a delivery surface over published datasets.

## Current implementation

- `app/streamlit_app.py` is the Streamlit entrypoint.
- `src/ebird_platform/app/legacy_dashboard.py` is the compatibility module that keeps the current UI and metric behavior.
- `src/ebird_platform/settings.py` resolves paths for local development, publication artifacts, and legacy fallback.
- `src/ebird_platform/pipeline/validate.py` validates the required directory structure for the app-facing datasets.
