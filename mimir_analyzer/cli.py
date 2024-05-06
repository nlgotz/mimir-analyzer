"""Example cli using click."""

import json
import logging
import re
import subprocess
import time
from pathlib import Path
from typing import List, Optional

import click
import httpx

from mimir_analyzer.config import Settings
from mimir_analyzer.log import initialize_logging

# Import necessary project related things to use in CLI

log = logging.getLogger(__name__)
settings = Settings()


def convert_to_seconds(input_time: str) -> int:
    """Convert time format to seconds.

    60s = 60
    1m = 60
    1h = 3600

    Args:
        time (str): Time input.

    Returns:
        int: time format as an integer.
    """
    if not re.match("^[0-9]+(s|m|h|d|w)$", input_time):
        raise ValueError("Time does not match a valid pattern.")

    time_suffix: str = input_time[-1:]
    time_value: int = int(input_time[:-1])

    if time_suffix == "m":
        time_value *= 60
    elif time_suffix == "h":
        time_value *= 3600
    elif time_suffix == "d":
        time_value *= 86400
    elif time_suffix == "w":
        time_value *= 604800

    return time_value


def get_tenants(server: str) -> List[str]:
    """Get list of tenants for Mimir server.

    Args:
        server (str): Server base URL

    Returns:
        List[str]: List of servers
    """
    headers: dict = {"Accept": "application/json"}
    url = f"{server}/store-gateway/tenants"
    with httpx.Client() as client:
        data: httpx.Response = client.get(url, headers=headers)

    return data.json().get("tenants")


def _run_mimirtool_collection(tenants: List[str]) -> None:
    """Run the mimirtool analyzer function for all the needed tenants.

    Args:
        tenants (List[str]): List of tenants to analyze.
    """
    subprocess.run(
        [
            "mimirtool",
            "analyze",
            "grafana",
            "--address",
            f"{settings.grafana_address}",
            "--key",
            settings.grafana_api_token.get_secret_value(),
            "--output",
            "exports/metrics-in-grafana.json",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )

    for tenant in tenants:
        subprocess.run(
            [
                "mimirtool",
                "analyze",
                "ruler",
                "--address",
                f"{settings.mimir_address}",
                "--id",
                tenant,
                "--output",
                f"exports/{tenant}.metrics-in-ruler.json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        subprocess.run(
            [
                "mimirtool",
                "analyze",
                "prometheus",
                "--address",
                f"{settings.mimir_address}",
                "--prometheus-http-prefix",
                "prometheus",
                "--id",
                tenant,
                "--grafana-metrics-file",
                "exports/metrics-in-grafana.json",
                "--ruler-metrics-file",
                f"exports/{tenant}.metrics-in-ruler.json",
                "--output",
                f"exports/{tenant}.prometheus-metrics.json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )


def _mimir_analyzer(tenants: List[str], output: Optional[str] = None) -> None:
    """Run the Mimir Analyzer."""
    

    # Collect Information
    _run_mimirtool_collection(tenants)

    metric_status: dict = {}
    for tenant in tenants:

        with open(f"exports/{tenant}.prometheus-metrics.json", "r", encoding="utf-8") as file:
            metrics = json.load(file)

        tenant_metrics: dict = {
            "total_metric_count": 0,
            "in_use_metric_count": 0,
            "not_in_use_metric_count": 0,
            "active_series": {
                "total": metrics.get("total_active_series", 0),
                "in_use": metrics.get("in_use_active_series", 0),
                "not_in_use": metrics.get("additional_active_series", 0),
            },
            "in_use": [],
            "not_in_use": [],
        }

        if metrics.get("in_use_metric_counts", []) is not None:
            tenant_metrics["in_use"] = sorted([metric["metric"] for metric in metrics["in_use_metric_counts"]])
        if metrics.get("additional_metric_counts", []) is not None:
            tenant_metrics["not_in_use"] = sorted([metric["metric"] for metric in metrics["additional_metric_counts"]])

        tenant_metrics["total_metric_count"] = len(tenant_metrics["in_use"]) + len(tenant_metrics["not_in_use"])
        tenant_metrics["in_use_metric_count"] = len(tenant_metrics["in_use"])
        tenant_metrics["not_in_use_metric_count"] = len(tenant_metrics["not_in_use"])

        metric_status[tenant] = tenant_metrics

    log.info(msg=json.dumps(metric_status))
    if output:
        with open(f"exports/{output}", "w", encoding="utf-8") as file:
            json.dump(metric_status, file, indent=4)


@click.command()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    help="Logging level",
)
@click.option("--log-file", default=None, help="Log file to output to debug logs to")
@click.option("--interval", help="How often to run")
@click.option("--output", help="File to save output to")
@click.option("--tenants", help="Comma Separated List of Tenants")
def main(log_level, log_file, interval, output, tenants):
    """Entrypoint into CLI app."""
    initialize_logging(level=log_level, filename=log_file)
    log.info("Entrypoint of the CLI app.")

    interval: int = interval or settings.interval
    output: str = output or settings.output
    if tenants:
        tenants: List[str] = tenants.split(",")
    else:
        tenants: List[str] = get_tenants(settings.mimir_address)

    run: bool = True

    if interval:
        interval = convert_to_seconds(interval)
        log.info("Running every %ss", interval)

    Path("exports").mkdir(parents=True, exist_ok=True)

    while run:
        _mimir_analyzer(tenants, output)
        if not interval:
            run = False
        else:
            log.debug("Sleeping for %ss", interval)
            time.sleep(interval)


if __name__ == "__main__":
    main()  # pylint: disable=no-value-for-parameter
