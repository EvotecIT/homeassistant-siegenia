# Releasing Siegenia for Home Assistant

A short, repeatable checklist to cut a clean release and wrap things up nicely.

## 0) Prereqs
- Home Assistant compatibility: validated against 2025.9.x (and 2025.8.x in CI).
- HACS metadata present (`hacs.json`).
- Brands PR prepared (see `docs/brands-pr/README.md`).

## 1) Version bump
- Update `custom_components/siegenia/manifest.json` → `version` (semver).

## 2) Validate locally
- Create venv and run tests:
  - `pip install -r requirements_test.txt`
  - `pytest -q`
- Validate workflows:
  - hassfest: `gh workflow run hassfest.yml` (or wait for CI on push)
  - HACS validation runs via CI (`validate-hacs.yml`).

## 3) Brands assets (optional, but recommended)
- Generate PNGs from SVGs:
  - `.venv/bin/python tools/gen_brand_icons.py`
  - Confirms files in `build/brand/`.
- Submit PR to `home-assistant/brands` (see `docs/brands-pr/README.md`).
- After merge, consider removing the local PNG serving fallback from `__init__.py` in a future release.

## 4) Tag and Release
- Commit the version bump.
- Create a signed tag: `git tag -a vX.Y.Z -m "Siegenia vX.Y.Z" && git push --tags`.
- Create a GitHub Release and write the changelog in the release notes.

## 5) HACS
- If not yet on the default HACS list, users can add this repo as a custom repository.
- After a few stable releases + branding merged, consider submitting to HACS default.

## 6) Post‑release
- Verify installation on a fresh HA instance via HACS (or manual) works.
- Check Integrations page icon appears (brands PR/CDN can take time).
- Triage any incoming issues; label with `bug`, `enhancement`, `question`.

## Migration Notes Checklist (for Releases)
- Entity IDs: If you used the built‑in “Recreate entity ID”, IDs may change to `<device>_<entity>`; update any automations.
- Legacy `_none` IDs: Use HA’s tool or `siegenia.repair_names` (optional) to normalize.
- Options: New Options may reset to defaults; review `Settings → Integrations → Siegenia → Configure`.

---
Maintainers: keep releases small and focused. Avoid mixing refactors with features in the same release.
