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
  scenario generation
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
- `/v1/distributions/generate`
- `/v1/scenarios/sample`
- `/v1/scenarios/generate`
- `/v1/presets`
- `/v1/presets/{preset_id}/generate`

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
  "seed": 42
}
```

### Distribution Generate

```json
{
  "action": "/v1/distributions/generate",
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

Providing a `seed` makes distribution outputs deterministic for the same request.

### Scenario Sample

`/v1/scenarios/sample` returns one event and only accepts stateless injectors. Right now that means rate-based or count-based selection with any supported mutation.

```json
{
  "action": "/v1/scenarios/sample",
  "name": "simple_sample",
  "seed": 11,
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
    }
  ],
  "injectors": [
    {
      "injector_id": "always_scale",
      "field": "value",
      "selection": {
        "kind": "rate",
        "rate": 1.0
      },
      "mutation": {
        "kind": "scale",
        "factor": 2.0
      }
    }
  ]
}
```

### Scenario Generate

```json
{
  "action": "/v1/scenarios/generate",
  "name": "simple_generate",
  "seed": 11,
  "row_count": 100,
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
      "injector_id": "random_spikes",
      "field": "value",
      "selection": {
        "kind": "count",
        "count": 3
      },
      "mutation": {
        "kind": "offset",
        "min_amount": 5.0,
        "max_amount": 12.0
      }
    }
  ]
}
```

Injected rows keep mutation provenance in their labels. Each label includes the pre-mutation value, the post-mutation value, and the actual mutation parameters sampled for that row.

Offset mutations accept either a fixed `amount` or a ranged `min_amount` / `max_amount`. Scale mutations accept either a fixed `factor` or a ranged `min_factor` / `max_factor`; for example, `factor: 1.2` means a 20% increase.

Providing a `seed` makes scenario outputs deterministic for the same request. If `time.start` is omitted on a seeded scenario, the engine uses a fixed UTC baseline so event timestamps are deterministic too.

### List Presets

```json
{
  "action": "/v1/presets"
}
```

### Preset Generate

```json
{
  "action": "/v1/presets/transaction_benchmark/generate",
  "seed": 3,
  "row_count": 12,
  "overrides": {
    "anomaly_rate": 0.08,
    "regime_start_index": 6
  }
}
```

### Lambda Invoke Example

```bash
aws lambda invoke \
  --function-name data-simulator-api-dev \
  --cli-binary-format raw-in-base64-out \
  --payload '{"action":"/v1/distributions/generate","distribution":"normal","parameters":{"mean":10.0,"stddev":2.0},"count":5,"seed":42,"summary":true}' \
  /tmp/data-simulator-sample.json
```

## Manual Smoke Test

Run a few end-to-end checks against the deployed Lambda:

```bash
./scripts/smoke_test_lambda.sh
```

Pass a different function name if needed:

```bash
./scripts/smoke_test_lambda.sh data-simulator-api-prod
```

## Private API Deployment

The `dev` stack can also create a private REST API Gateway in front of the Lambda.
That API is scoped to the shared dev VPC published by `aws_infra`, but it is not tied
to a specific `execute-api` VPC endpoint ID. Recreating the endpoint layer should not
require reapplying this repo as long as the shared VPC stays the same.

When the shared endpoint stack also publishes the `dev.internal` private hosted zone,
this stack creates `simulator-api.dev.internal` as a readable internal name for the API.
The URL still includes the stage path, for example `https://simulator-api.dev.internal/dev`.

The hosted zone lives in `aws_infra`, so tearing down the shared endpoint stack also
removes the internal DNS layer. Recreating that stack requires reapplying this repo so
the API record can be recreated in the new hosted zone.

## Design Notes

- `handler.py` should stay thin.
- request validation belongs in `api`
- simulation logic belongs in `engine`
- preset definitions should compose the engine rather than bypass it
