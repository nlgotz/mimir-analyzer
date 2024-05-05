# Mimir Analyzer

Mimir Analyzer is a tool designed to help determine what metrics are being used for each tenant on a Mimir install.

## Running

```bash
cat << EOF > mimir-analyzer.env
MIMIR_ANALYZER_GRAFANA_ADDRESS=https://grafana.example.com
MIMIR_ANALYZER_GRAFANA_API_TOKEN=glsa_123abc
MIMIR_ANALYZER_MIMIR_ADDRESS=https://mimir.example.com
EOF

mkdir exports
docker run -u `id -u $USER` --env-file $(pwd)/mimir-analyzer.env -it --rm -v $(pwd)/exports:/local/exports ghcr.io/nlgotz/mimir-analyzer:latest mimir_analyzer --output=output.json
```

## Sample Output

Using the commands above, you can expect an output.json file similar to:

```json
{
    "tenant_1": {
        "total_count": 4,
        "in_use_count": 3,
        "not_in_use_count": 1,
        "in_use": [
            "metric_1",
            "metric_2",
            "metric_4"
        ],
        "not_in_use": [
            "metric_3"
        ]
    },
    "tenant_2": {
        "total_count": 4,
        "in_use_count": 1,
        "not_in_use_count": 3,
        "in_use": [
            "metric_3"
        ],
        "not_in_use": [
            "metric_1",
            "metric_2",
            "metric_4"
        ]
    }
}
```
