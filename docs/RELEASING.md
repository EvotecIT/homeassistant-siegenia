# Releasing Siegenia for Home Assistant

Siegenia releases are prepared automatically after a pull request is merged.
PowerForge updates the integration and Python package versions, builds the
release commit, creates the tag, and publishes the GitHub release.

## Normal release

1. Open a release-ready pull request.
2. Let CI, Hassfest, and HACS validation finish.
3. Merge the pull request.
4. Verify the `Release` workflow completed.
5. Verify the public tag and release, and confirm that
   `custom_components/siegenia/manifest.json` and `pyproject.toml` have the same
   version on the default branch.

The shared release workflow selects the version increment from the pull request.
Ordinary fixes default to a patch release.

## Recovery

If the automatic workflow did not start or needs a controlled retry, dispatch
the `Release` workflow with:

- the merged pull request number
- its verified merge commit SHA
- `increment: patch`, `minor`, or `major` as appropriate

Do not dispatch a recovery while an automatic release is still pending. This
avoids publishing two version increments for one pull request.

## Validation before merge

```bash
python -m pip install -r requirements_test.txt
python -m compileall siegenia_client custom_components tests examples
pytest
```

CI also exercises the repository's current Home Assistant test lane. Release
work should remain focused; unrelated features belong in separate pull requests.
