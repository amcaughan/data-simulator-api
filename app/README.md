# Application Runtime

This package contains the Lambda application code for the data simulator API.

## Structure

- `handler.py`
  Lambda entrypoint
- `api/models.py`
  typed request and scenario models
- `api/router.py`
  route resolution and request handling
- `engine/distributions.py`
  primitive distribution sampling and summaries
- `engine/scenario.py`
  scenario preview generation
- `engine/injectors.py`
  anomaly and benchmark injection logic
- `engine/presets.py`
  built-in preset scenarios
- `requirements.in`
  direct runtime dependencies
- `requirements.txt`
  pinned runtime dependency lockfile

## Current API Surface

- `health`
- `/v1/distributions/sample`
- `/v1/scenarios/preview`
- `/v1/presets`
- `/v1/presets/{preset_id}/preview`

## Design Notes

- `handler.py` should stay thin.
- request validation belongs in `api`
- simulation logic belongs in `engine`
- preset definitions should compose the engine rather than bypass it
