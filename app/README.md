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
- `engine/entities.py`
  entity pools and stable per-row entity assignment
- `engine/process_modifiers.py`
  generation-time cross-row parameter adjustments
- `engine/mutations.py`
  post-generation row mutations
- `engine/scenario.py`
  scenario generation
- `engine/presets.py`
  built-in preset scenarios
- `requirements.in`
  direct runtime dependencies
- `requirements.txt`
  pinned runtime dependency lockfile

## Current API Surface

- `GET /health`
- `POST /v1/distributions/sample`
- `POST /v1/distributions/generate`
- `POST /v1/scenarios/sample`
- `POST /v1/scenarios/generate`
- `GET /v1/presets`
- `POST /v1/presets/{preset_id}/generate`

## Sample Requests

HTTP callers should use the methods above and send the JSON body without an `action`
field. The `action` examples below are direct Lambda invocation payloads, which are
still useful for local smoke testing and `aws lambda invoke`.

The private API Gateway methods use `AWS_IAM` authorization. Internal callers should
use SigV4-signed requests from an AWS principal that has `execute-api:Invoke`
permission, typically an ECS task role or another workload role inside the shared VPC.

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

`/v1/scenarios/sample` returns one row and only accepts sample-compatible process modifiers and mutations. Right now that means rate-based or count-based selection.

```json
{
  "action": "/v1/scenarios/sample",
  "name": "simple_sample",
  "seed": 11,
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
  "mutations": [
    {
      "mutation_id": "always_scale",
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
  "mutations": [
    {
      "mutation_id": "random_spikes",
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

Generated rows keep label provenance for both generation-time process modifiers and post-generation mutations. Mutation labels include the pre-mutation value, the post-mutation value, and the actual mutation parameters sampled for that row. Process modifier labels include the applied parameter adjustments and the final generated value.

Offset mutations accept either a fixed `amount` or a ranged `min_amount` / `max_amount`. Scale mutations accept either a fixed `factor` or a ranged `min_factor` / `max_factor`; for example, `factor: 1.2` means a 20% increase.

Providing a `seed` makes scenario outputs deterministic for the same request.

### Sequence Fields

`sequence` is the generic row-by-row counter primitive. It is useful for things like
batch record numbers, row offsets, simple synthetic IDs, or poll counters.

```json
{
  "action": "/v1/scenarios/generate",
  "name": "sequence_generate",
  "seed": 13,
  "row_count": 4,
  "fields": [
    {
      "name": "customer_id",
      "generator": {
        "kind": "sequence",
        "start": 1000,
        "step": 5
      }
    }
  ]
}
```

### Scenario Generate With Entities

Entity pools make it possible to emit repeated IDs, stable per-entity dimensions, and
stable hidden entity attributes that can shape row-level distributions. That is useful
for downstream ELT work because the generated rows can be grouped by things like
`customer_id`, `merchant_id`, `device_id`, or `product_id`, while still behaving
slightly differently by segment or entity.

```json
{
  "action": "/v1/scenarios/generate",
  "name": "entity_generate",
  "seed": 29,
  "row_count": 12,
  "entity_pools": [
    {
      "name": "customers",
      "count": 3,
      "id_prefix": "customer",
      "attributes": [
        {
          "name": "customer_region",
          "generator": {
            "kind": "categorical",
            "values": ["west", "south", "northeast"]
          }
        },
        {
          "name": "loyalty_tier",
          "generator": {
            "kind": "categorical",
            "values": ["standard", "gold"],
            "weights": [0.8, 0.2]
          }
        }
      ]
    }
  ],
  "fields": [
    {
      "name": "customer_id",
      "generator": {
        "kind": "entity_id",
        "entity_name": "customers"
      }
    },
    {
      "name": "customer_region",
      "generator": {
        "kind": "entity_attribute",
        "entity_name": "customers",
        "attribute": "customer_region"
      }
    },
    {
      "name": "loyalty_tier",
      "generator": {
        "kind": "entity_attribute",
        "entity_name": "customers",
        "attribute": "loyalty_tier"
      }
    },
    {
      "name": "amount",
      "generator": {
        "kind": "contextual_distribution",
        "distribution": "lognormal",
        "parameters": {
          "mean": 3.5,
          "stddev": 0.3
        },
        "parameter_modifiers": [
          {
            "parameter": "mean",
            "operation": "add",
            "value": 0.4,
            "when": [
              {
                "field": "loyalty_tier",
                "equals": "gold"
              }
            ]
          }
        ]
      }
    }
  ]
}
```

`contextual_distribution` starts from a normal distribution definition and then adjusts
one or more distribution parameters per row. Modifiers can use:

- a fixed numeric `value`
- an earlier generated `source_field`
- a hidden `entity_name` / `entity_attribute` value from an entity pool

Modifiers are applied in order, so the request stays readable.

### Process Modifiers And Scoped Mutations

Process modifiers are applied during generation and are best for things like regime
shifts or drift windows. Mutations are applied after generation and are best for
dropouts, spikes, or forced value changes.

```json
{
  "action": "/v1/scenarios/generate",
  "name": "scoped_generate",
  "seed": 43,
  "row_count": 6,
  "fields": [
    {
      "name": "segment",
      "generator": {
        "kind": "categorical",
        "values": ["target", "other"],
        "weights": [0.5, 0.5]
      }
    },
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
  "mutations": [
    {
      "mutation_id": "target_only",
      "field": "value",
      "scope": [
        {
          "field": "segment",
          "equals": "target"
        }
      ],
      "selection": {
        "kind": "count",
        "count": 1
      },
      "mutation": {
        "kind": "offset",
        "amount": 5.0
      }
    }
  ]
}
```

### Example Modeling Patterns

These examples are meant to show how the current request model can express useful
scenarios for ELT, analytics, and benchmark datasets.

#### Card Takeover Window

This pattern approximates a card that normally behaves like a standard retail card,
then shifts into an online, high-risk period with larger amounts and more declines.

```json
{
  "action": "/v1/scenarios/generate",
  "name": "card_takeover",
  "seed": 77,
  "row_count": 120,
  "entity_pools": [
    {
      "name": "cards",
      "count": 12,
      "id_prefix": "card",
      "attributes": [
        {
          "name": "card_segment",
          "generator": {
            "kind": "categorical",
            "values": ["standard", "premium"],
            "weights": [0.85, 0.15]
          }
        },
        {
          "name": "spend_bias",
          "generator": {
            "kind": "distribution",
            "distribution": "normal",
            "parameters": {
              "mean": 0.0,
              "stddev": 0.18
            }
          }
        }
      ]
    }
  ],
  "fields": [
    {
      "name": "card_id",
      "generator": {
        "kind": "entity_id",
        "entity_name": "cards"
      }
    },
    {
      "name": "card_segment",
      "generator": {
        "kind": "entity_attribute",
        "entity_name": "cards",
        "attribute": "card_segment"
      }
    },
    {
      "name": "channel",
      "generator": {
        "kind": "categorical",
        "values": ["card_present", "online"],
        "weights": [0.75, 0.25]
      }
    },
    {
      "name": "amount",
      "generator": {
        "kind": "contextual_distribution",
        "distribution": "lognormal",
        "parameters": {
          "mean": 4.0,
          "stddev": 0.35
        },
        "parameter_modifiers": [
          {
            "parameter": "mean",
            "operation": "add",
            "entity_name": "cards",
            "entity_attribute": "spend_bias"
          },
          {
            "parameter": "mean",
            "operation": "add",
            "value": 0.25,
            "when": [
              {
                "field": "channel",
                "equals": "online"
              }
            ]
          }
        ]
      }
    },
    {
      "name": "is_declined",
      "generator": {
        "kind": "contextual_distribution",
        "distribution": "bernoulli",
        "parameters": {
          "probability": 0.03
        },
        "parameter_modifiers": [
          {
            "parameter": "probability",
            "operation": "multiply",
            "value": 1.8,
            "when": [
              {
                "field": "channel",
                "equals": "online"
              }
            ]
          }
        ]
      }
    }
  ],
  "process_modifiers": [
    {
      "modifier_id": "takeover_window",
      "field": "amount",
      "scope": [
        {
          "field": "channel",
          "equals": "online"
        }
      ],
      "selection": {
        "kind": "window",
        "start_index": 80,
        "end_index": 110
      },
      "parameter_modifiers": [
        {
          "parameter": "mean",
          "operation": "add",
          "value": 0.6
        }
      ]
    }
  ]
}
```

#### Sensor Fleet With Device-Level Bias

This pattern models a sensor fleet where each device has its own calibration offset and
noise profile, and a subset of pressure sensors experience a dropout window.

```json
{
  "action": "/v1/scenarios/generate",
  "name": "sensor_fleet",
  "seed": 101,
  "row_count": 180,
  "entity_pools": [
    {
      "name": "devices",
      "count": 18,
      "id_prefix": "device",
      "attributes": [
        {
          "name": "device_type",
          "generator": {
            "kind": "categorical",
            "values": ["thermometer", "pressure_sensor", "combo_sensor"],
            "weights": [0.35, 0.25, 0.4]
          }
        },
        {
          "name": "temperature_offset",
          "generator": {
            "kind": "distribution",
            "distribution": "normal",
            "parameters": {
              "mean": 0.0,
              "stddev": 0.45
            }
          }
        },
        {
          "name": "noise_multiplier",
          "generator": {
            "kind": "categorical",
            "values": [0.8, 1.0, 1.25],
            "weights": [0.2, 0.55, 0.25]
          }
        }
      ]
    }
  ],
  "fields": [
    {
      "name": "device_id",
      "generator": {
        "kind": "entity_id",
        "entity_name": "devices"
      }
    },
    {
      "name": "device_type",
      "generator": {
        "kind": "entity_attribute",
        "entity_name": "devices",
        "attribute": "device_type"
      }
    },
    {
      "name": "temperature_c",
      "generator": {
        "kind": "contextual_distribution",
        "distribution": "normal",
        "parameters": {
          "mean": 22.0,
          "stddev": 0.6
        },
        "parameter_modifiers": [
          {
            "parameter": "mean",
            "operation": "add",
            "entity_name": "devices",
            "entity_attribute": "temperature_offset"
          },
          {
            "parameter": "stddev",
            "operation": "multiply",
            "entity_name": "devices",
            "entity_attribute": "noise_multiplier"
          }
        ]
      }
    }
  ],
  "mutations": [
    {
      "mutation_id": "pressure_dropout",
      "field": "temperature_c",
      "scope": [
        {
          "field": "device_type",
          "equals": "pressure_sensor"
        }
      ],
      "selection": {
        "kind": "window",
        "start_index": 90,
        "end_index": 110
      },
      "mutation": {
        "kind": "set_missing"
      }
    }
  ]
}
```

#### Orders With Segment and Product Effects

This pattern models order amounts and returns with both customer- and product-level
effects. It is useful for testing dbt models that aggregate by customer, product,
region, price band, or return rate.

```json
{
  "action": "/v1/scenarios/generate",
  "name": "order_flow",
  "seed": 202,
  "row_count": 150,
  "entity_pools": [
    {
      "name": "customers",
      "count": 20,
      "attributes": [
        {
          "name": "loyalty_tier",
          "generator": {
            "kind": "categorical",
            "values": ["standard", "silver", "gold"],
            "weights": [0.65, 0.23, 0.12]
          }
        }
      ]
    },
    {
      "name": "products",
      "count": 25,
      "attributes": [
        {
          "name": "product_category",
          "generator": {
            "kind": "categorical",
            "values": ["apparel", "electronics", "home", "beauty"]
          }
        },
        {
          "name": "price_band",
          "generator": {
            "kind": "categorical",
            "values": ["budget", "midrange", "premium"],
            "weights": [0.4, 0.42, 0.18]
          }
        }
      ]
    }
  ],
  "fields": [
    {
      "name": "customer_id",
      "generator": {
        "kind": "entity_id",
        "entity_name": "customers"
      }
    },
    {
      "name": "loyalty_tier",
      "generator": {
        "kind": "entity_attribute",
        "entity_name": "customers",
        "attribute": "loyalty_tier"
      }
    },
    {
      "name": "product_id",
      "generator": {
        "kind": "entity_id",
        "entity_name": "products"
      }
    },
    {
      "name": "product_category",
      "generator": {
        "kind": "entity_attribute",
        "entity_name": "products",
        "attribute": "product_category"
      }
    },
    {
      "name": "price_band",
      "generator": {
        "kind": "entity_attribute",
        "entity_name": "products",
        "attribute": "price_band"
      }
    },
    {
      "name": "order_amount",
      "generator": {
        "kind": "contextual_distribution",
        "distribution": "lognormal",
        "parameters": {
          "mean": 3.8,
          "stddev": 0.42
        },
        "parameter_modifiers": [
          {
            "parameter": "mean",
            "operation": "add",
            "value": 0.3,
            "when": [
              {
                "field": "price_band",
                "equals": "premium"
              }
            ]
          },
          {
            "parameter": "mean",
            "operation": "add",
            "value": -0.08,
            "when": [
              {
                "field": "loyalty_tier",
                "equals": "gold"
              }
            ]
          }
        ]
      }
    },
    {
      "name": "is_returned",
      "generator": {
        "kind": "contextual_distribution",
        "distribution": "bernoulli",
        "parameters": {
          "probability": 0.08
        },
        "parameter_modifiers": [
          {
            "parameter": "probability",
            "operation": "multiply",
            "value": 1.4,
            "when": [
              {
                "field": "product_category",
                "equals": "apparel"
              }
            ]
          },
          {
            "parameter": "probability",
            "operation": "multiply",
            "value": 0.7,
            "when": [
              {
                "field": "loyalty_tier",
                "equals": "gold"
              }
            ]
          }
        ]
      }
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

### Batch Delivery Preset

`batch_delivery_benchmark` is meant for ELT-style file drops. One API call can be
treated as one delivered file from one client. To simulate multiple clients or
multiple deliveries, call the same preset again with a different `source_system_id`,
`delivery_id`, `delivery_date`, and optionally a different seed.

```json
{
  "action": "/v1/presets/batch_delivery_benchmark/generate",
  "seed": 19,
  "row_count": 8,
  "overrides": {
    "source_system_id": "hospital_system_a",
    "delivery_id": "hospital_system_a_20260312",
    "delivery_date": "2026-03-12",
    "feed_type": "member_snapshot",
    "facility_count": 3
  }
}
```

The returned rows are shaped more like a delivered batch than a time series. They
include repeated batch metadata such as `source_system_id`, `delivery_id`, and
`delivery_date`, plus row-level fields such as `record_number`, `member_id`,
`facility_id`, `plan_tier`, and `allowed_amount`.

Current presets:
- `batch_delivery_benchmark`
  one batch-delivered client file per API call, with source-system, delivery, facility, and member-style fields
- `transaction_benchmark`
  card and merchant IDs with stable merchant and card dimensions, plus a generation-time amount regime shift
- `iot_sensor_benchmark`
  device and site IDs with telemetry mutations and a generation-time pressure regime shift
- `order_benchmark`
  customer and product IDs with generation-time marketplace shifts and fulfillment mutations

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
That API is scoped to the shared dev VPC published by `aws_infra`, uses explicit route
definitions at the API Gateway layer, and requires `AWS_IAM` authorization on every
method. It is not tied to a specific `execute-api` VPC endpoint ID. Recreating the
endpoint layer should not require reapplying this repo as long as the shared VPC stays
the same.

## Design Notes

- `handler.py` should stay thin.
- request validation belongs in `api`
- simulation logic belongs in `engine`
- preset definitions should compose the engine rather than bypass it
