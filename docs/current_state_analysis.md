# Current State Analysis And Recommended Next Phase

## Objective

This document consolidates the current technical state of the project, the operational interpretation of the public app link, the real bottleneck observed so far, and a recommended architecture for the next phase.

It is based on the repository state as of March 12, 2026.

## Executive summary

- The current app is a Streamlit delivery layer over curated datasets that are already published in the repository under `published/data`, with fallback to the legacy local repository.
- If the public URL is hosted on Streamlit Community Cloud, there is typically no direct per-visitor billing model for each app access. The immediate issue is not traffic cost; it is data freshness.
- The current repository already points toward an S3-first data publication model. The next logical step is to automate data refresh outside Git and keep GitHub focused on source code.
- The recommended next phase is: `EventBridge -> Lambda -> eBird API -> curated Parquet outputs -> S3 -> Streamlit`.

## Current deployment interpretation

The repository documents the first public deployment path as `GitHub + Streamlit Community Cloud` in [deploy_streamlit_cloud.md](/D:/ebird-platform/docs/deploy_streamlit_cloud.md). The same documentation states that the app expects data from either:

- `EBIRD_DATA_DIR`
- `published/data`

This means the deployed app is currently designed to run from a static published snapshot of curated data, not from a live data pipeline.

## Cost interpretation of the public app link

For the currently documented deployment model:

- Opening the public Streamlit link does not imply a direct usage-based charge per visitor in the application codebase.
- The project does not currently contain any architecture that would create per-access AWS Lambda or API invocation cost from each page load.
- The app mostly reads local or published Parquet data through cached loaders, which reinforces the interpretation that it is serving a prepared snapshot.

Operationally, the main problem is therefore not link traffic cost. The main problem is that the published datasets become stale unless they are republished.

## Real current bottleneck

The project structure strongly indicates that the current bottleneck is data refresh, not app rendering.

Reasons:

- `src/ebird_platform/settings.py` resolves data from a fixed priority list and prefers published artifacts when present.
- `src/ebird_platform/io/loaders.py` reads Parquet datasets from the resolved directories and caches them with `st.cache_data`.
- `published/data` already contains curated app-facing outputs.
- The repository contains validation and publishing notes, but not a full automated ingestion pipeline from eBird API into AWS-managed refresh jobs.

In practice:

- The app can be online and functional.
- The visual layer can be correct.
- The data can still be outdated because the published snapshot has not been refreshed.

## Project analysis

## 1. Architecture

The project is already organized around a clean separation of concerns:

- `app/streamlit_app.py`: Streamlit entrypoint.
- `src/ebird_platform/settings.py`: path resolution and deployment portability.
- `src/ebird_platform/io/loaders.py`: dataset loading, schema normalization, caching, and fallback handling.
- `src/ebird_platform/app/*.py`: UI and analytical views.
- `src/ebird_platform/pipeline/validate.py`: validation of required published data structure.
- `published/data`: curated app-facing artifacts.
- `docs/`: deployment and infrastructure guidance.

This is a sound direction. The app is already being treated as a consumer of prepared analytical outputs instead of a monolith that recomputes everything at runtime.

## 2. Data access model

The current data access strategy is pragmatic and works well for migration:

- First preference: `EBIRD_DATA_DIR`
- Second preference: repository publication artifacts under `published/data`
- Fallbacks: legacy local data directories under `D:/eBird`

Strengths:

- Supports local development and public deployment with minimal code changes.
- Preserves legacy compatibility.
- Allows small curated outputs to be shipped with the app.

Risks:

- The fallback chain is still partly coupled to the old local environment.
- Production freshness depends on external manual publication discipline.
- There is not yet a repository-native concept of dataset version, publication timestamp, or freshness SLA.

## 3. Application behavior

The current user-facing product is richer than a simple map app. It already includes:

- Territorial richness maps by state and municipality.
- Ecological analysis tables by city.
- Temporal analysis.
- Similarity analysis across cities using Jensen-Shannon and Jaccard.

This is a meaningful analytical surface, not just a prototype shell.

Strengths:

- The business logic is explicit in code.
- The analytical pages are split into separate modules.
- The map layer includes fallback metric generation from the city-species cube when precomputed artifacts are incomplete.

Risks:

- Several strings in the UI are visibly mojibake-affected, which suggests an encoding issue in source text or terminal history.
- Some analytical fallback behavior is embedded directly in the UI layer, which may become harder to maintain as the pipeline grows.
- The compatibility module `legacy_dashboard.py` still exists, which is useful for migration but indicates unfinished consolidation.

## 4. Dataset contract quality

`loaders.py` shows deliberate defensive handling of schema variation:

- alternative column names are normalized,
- missing columns are synthesized when possible,
- legacy filenames are still supported,
- CRS is normalized for geospatial data.

This is a strong migration pattern because it makes the app resilient to moderate upstream schema drift.

However, there are also signals that the data contract is still evolving:

- multiple file naming conventions are accepted,
- some loaders depend on fallback heuristics,
- some metrics are computed from alternative sources if the preferred artifact is absent or empty.

That is acceptable in transition, but the next phase should reduce ambiguity.

## 5. Operational maturity

The repository already has the right direction for operations:

- local validation script,
- app run script,
- deployment note for Streamlit Cloud,
- bootstrap note for AWS S3 publication.

What is still missing for a production-grade pipeline:

- automated scheduled refresh,
- automated publish to S3,
- freshness metadata,
- monitoring and alerting,
- secret management for the eBird API key,
- a deployment path where the app consumes remote published data without repository churn.

## 6. Testing posture

Current automated test coverage is minimal.

Observed test scope:

- `tests/test_settings.py` only validates basic path resolution and asset existence.

This means there is currently little automated protection for:

- dataset contract regressions,
- loader fallback behavior,
- map assembly logic,
- analytical metric assumptions,
- deployment path differences.

This is the biggest technical gap inside the codebase today.

## 7. Overall assessment

The project is in a good transitional state:

- It is already usable.
- It is already structured better than the legacy monolith.
- It has a clear deployment story for a first public release.

But it is not yet a fully automated data product platform.

The main missing capability is not frontend polish. It is reliable, scheduled, observable data publication.

## Recommended next phase

## Recommended target flow

The recommended architecture for the next stage is:

1. `Amazon EventBridge` triggers the refresh schedule.
2. `AWS Lambda` calls the eBird API.
3. The Lambda job transforms raw responses into the curated Parquet outputs expected by the app.
4. The outputs are written to `Amazon S3`.
5. The Streamlit app reads the curated published outputs from S3, with caching.

## Why this is better than "GitHub pulling from AWS"

GitHub should remain the source of truth for code, documentation, and infrastructure definitions. It should not be the transport layer for frequently refreshed analytical data.

Using GitHub as the mechanism to move refreshed data into the app would create avoidable problems:

- unnecessary repository churn,
- large binary artifact growth,
- noisy commit history,
- redeploy coupling between code changes and data refresh,
- weaker separation between application lifecycle and publication lifecycle.

The cleaner split is:

- GitHub for code,
- AWS for scheduled data refresh and artifact publication,
- Streamlit for presentation.

## Recommended role of each platform

- `GitHub`: source code, infra definitions, documentation, CI for tests and linting.
- `EventBridge`: scheduling.
- `Lambda`: ingestion and transformation orchestration.
- `S3`: published curated data artifacts and versioned snapshots.
- `CloudWatch`: logs, metrics, failures, freshness checks.
- `Streamlit`: analytical UI consuming prepared data.

## Suggested implementation path

Phase 2 can be implemented incrementally:

### Step 1

Define the publication contract explicitly:

- exact file names,
- required columns,
- partitioning strategy if needed,
- version and freshness metadata.

### Step 2

Move the current publication artifacts to an S3 bucket while preserving the same directory contract expected by the app.

### Step 3

Create a Lambda job that:

- authenticates against the eBird API,
- fetches the required raw inputs,
- writes curated Parquet outputs,
- publishes them to S3 under a stable prefix such as `published/data/`.

### Step 4

Update the Streamlit app to read from S3-backed published outputs in production, while keeping local fallback for development.

### Step 5

Add observability:

- last successful refresh timestamp,
- dataset version identifier,
- failure alerting,
- optional in-app display of data freshness.

## Immediate repository recommendations

The next technical improvements inside this repository should be:

- Add documentation for the data contract and expected schemas per published artifact.
- Add tests for `loaders.py` normalization and fallback behavior.
- Add tests for `pipeline.validate`.
- Surface dataset freshness in the UI.
- Remove or isolate remaining legacy-specific assumptions as the AWS pipeline stabilizes.
- Fix source-text encoding issues visible in UI labels.

## Decision statement

The app is currently functional as a Streamlit analytics surface over published snapshots.

The current problem is primarily stale data, not visitor cost.

The next phase should not be "GitHub pulling from AWS" as the main operating model. The stronger architecture is:

`EventBridge -> Lambda -> eBird API -> curated Parquet -> S3 -> Streamlit`

That design is more scalable, cheaper to operate cognitively, easier to observe, and better aligned with the repository's documented direction.
