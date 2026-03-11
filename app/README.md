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

- `/health`
- `/v1/distributions/sample`
- `/v1/scenarios/preview`
- `/v1/presets`
- `/v1/presets/{preset_id}/preview`

## Sample Requests

### Health

```json
{
  "action": "/health"
}
```

### Distribution Sample

```json
{
  "action": "/v1/distributions/sample",
  "distribution": "normal",
  "parameters": {
    "mean": 10.0,
    "stddev": 2.0
  },
  "count": 5,
  "seed": 42,
  "summary": true
}
```

### Scenario Preview

```json
{
  "action": "/v1/scenarios/preview",
  "name": "simple_preview",
  "seed": 11,
  "row_count": 6,
  "time": {
    "frequency_seconds": 60
  },
  "fields": [
    {
      "name": "value",
      "generator": {
        "kind": "distribution",
        "distribution": "normal",
        "parameters": {
          "mean": 5.0,
          "stddev": 1.0
        }
      }
    },
    {
      "name": "status",
      "generator": {
        "kind": "categorical",
        "values": ["ok", "warn"],
        "weights": [0.8, 0.2]
      }
    }
  ],
  "injectors": [
    {
      "kind": "point_spike",
      "injector_id": "spike_1",
      "field": "value",
      "index": 2,
      "scale": 10.0
    }
  ]
}
```

### List Presets

```json
{
  "action": "/v1/presets"
}
```

### Preset Preview

```json
{
  "action": "/v1/presets/preview",
  "preset_id": "transaction_benchmark",
  "seed": 3,
  "row_count": 12,
  "overrides": {
    "anomaly_index": 3,
    "regime_start_index": 6
  }
}
```

### Lambda Invoke Example

```bash
aws lambda invoke \
  --function-name data-simulator-api-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"/v1/distributions/sample","distribution":"normal","parameters":{"mean":10.0,"stddev":2.0},"count":5,"seed":42,"summary":true}' \
  /tmp/data-simulator-sample.json
```

## Design Notes

- `handler.py` should stay thin.
- request validation belongs in `api`
- simulation logic belongs in `engine`
- preset definitions should compose the engine rather than bypass it
