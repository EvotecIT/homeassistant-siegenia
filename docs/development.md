# Development

[Back to the README](../README.md) · [Python library](python-library.md) ·
[Releasing](RELEASING.md)

## Local checks

```bash
python -m pip install -r requirements_test.txt
python -m pip install -e .
python -m compileall siegenia_client custom_components tests examples
pytest
```

CI validates the declared minimum HA 2026.7.2 and current stable HA 2026.9.4 on
Python 3.14. To reproduce the minimum lane, install
`requirements_test_minimum.txt` in a separate virtual environment. Normal local
checks use `requirements_test.txt`, which selects the current stable stack.
Home Assistant supplies compatible patched DNS dependencies; the old ACME and
DNS version overrides are unnecessary.

Keep the test plugin's resource-cleanup verification enabled. Shutdown and unload
tests exercise connection tasks, discovery tasks, push-idle and motion timers,
and late updates after unload. Unit tests do not establish device-connected
shutdown or full quality qualification.
The test session closes an idle pycares channel before cleanup baselines are
recorded, starting the patched library's single process-wide cleanup worker.
Per-test thread, task and timer checks remain enabled.

Each config entry owns its coordinator through typed `runtime_data`. Platforms
and diagnostics use that same object; successful unload stops its background
work, while a failed platform unload retains the running coordinator. Device
registry migration uses HA's supported registry helpers on both the minimum
and current test stacks.

Diagnostics redact credentials, host address, device identifiers, names, and
location fields while retaining model, firmware, and operating state. Tests
verify that redaction leaves the runtime snapshot and saved settings unchanged.
Review downloaded diagnostics before sharing them; source tests do not establish
privacy for every possible firmware payload.

Merged pull requests use the repository release workflow; see the
[release guide](RELEASING.md) for maintainer procedures.

## Ownership

`siegenia_client` owns the reusable controller API. The integration in
`custom_components/siegenia` owns Home Assistant setup, entities, and services.
The [Python library guide](python-library.md) includes direct-use examples; a
[runnable example](../examples/python_client.py) is also available.

Keep protocol notes and release procedures in docs. The README should introduce
the integration, explain installation and first setup, and link to the relevant
configuration, automation, and troubleshooting guides.

## Strict typing

The current-stable CI lane pins HA 2026.9.4 and its matching fixture release.
Install `requirements_test_latest.txt`, then run
`python -m mypy --strict custom_components/siegenia`. Mypy 2.4.0 checks all 21
production modules, including the bundled client. The only import exception is
HA's public `StaticPathConfig` re-export: it works on both supported endpoints,
but current HA does not explicitly expose it to strict type checkers. The minimum
lane proves runtime compatibility separately.

Device automation tests evaluate conditions and attach state-change triggers
through HA's own helpers. Name-repair tests verify that a completed dry run
produces its notification. These checks do not qualify device-connected actions.
The [rule ledger](quality.md) tracks remaining requirements.
