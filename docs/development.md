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

CI validates the supported Python lanes, the declared minimum HA 2024.8.0,
and a current Home Assistant stack. To reproduce the minimum lane, use Python
3.12 in a separate virtual environment and install
`requirements_test_minimum.txt` instead of `requirements_test.txt`.
The legacy test constraints keep the older HA stack compatible with its ACME
and DNS dependencies; they do not change the integration's runtime requirements.

Keep the test plugin's resource-cleanup verification enabled. Shutdown and unload
tests exercise connection tasks, discovery tasks, push-idle and motion timers,
and late updates after unload. Unit tests do not establish device-connected
shutdown or full quality qualification.

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
