# Development

[Back to the README](../README.md) · [Python library](python-library.md) ·
[Releasing](RELEASING.md)

## Local checks

```bash
python -m pip install -e .[test]
python -m compileall siegenia_client custom_components tests examples
pytest
```

CI validates the supported Python lanes and a current Home Assistant stack.
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
