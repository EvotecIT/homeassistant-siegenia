# Home Assistant Brands PR — Siegenia

Goal: submit official brand images so Home Assistant shows our logo/icon on the Integrations page without any code-side hacks.

This doc is a ready-to-use checklist for a PR to the `home-assistant/brands` repository.

## What Goes In The PR

- Location in brands repo: `custom_integrations/siegenia/`
- Required files (PNG, transparent background):
  - `icon.png` — 256×256
  - `logo.png` — 512×256 (wide logo; shortest side 256)
- Optional HiDPI files (recommended):
  - `icon@2x.png` — 512×512
  - `logo@2x.png` — 1024×512

Keep the artwork crisp, centered, with no padding or background. Do not use Home Assistant’s logo or other trademarks you don’t own.

References:
- Brands structure and rules (sizes, paths, transparency, naming): see the Home Assistant Brands README and “Creating Integration Brand” guide.

## Generate PNGs From Our SVG Sources

We keep masters in SVG under `assets/brand/`.

1) Ensure dependencies: `pip install cairosvg`
2) Run the helper:

```
python tools/gen_brand_icons.py
```

This writes PNGs to `build/brand/`:
- `build/brand/icon.png` (256×256)
- `build/brand/logo.png` (512×256)

If you want the `@2x` variants, re-run the conversion at 512 and 1024 widths, or export from your vector tool at those sizes and save as `icon@2x.png` and `logo@2x.png`.

## PR Steps (home-assistant/brands)

1) Fork `https://github.com/home-assistant/brands` and create a branch, e.g. `add-siegenia-brand`.
2) Create directory `custom_integrations/siegenia/`.
3) Copy in the generated PNGs:
   - `icon.png` (required)
   - `logo.png` (required)
   - `icon@2x.png` (optional)
   - `logo@2x.png` (optional)
4) Commit with a clear message, e.g. `Add brand assets for custom integration: siegenia`.
5) Open a PR. In the description, include:
   - A sentence confirming you own the artwork or have permission to use it.
   - Dimensions used and that images are PNG with transparent background.
   - A link to this integration repository for context.
6) Ensure the PR checks pass (the repo validates sizes, names, and transparency).

After the PR is merged and the CDN updates, Home Assistant will automatically show the brand images for our `siegenia` domain without any custom code.

## Temporary Placeholder Options (while PR is pending)

You have two non-invasive options so the tile isn’t blank locally:

- Preferred: use our generated PNGs locally
  - Run `python tools/gen_brand_icons.py` so `build/brand/icon.png` and `build/brand/logo.png` exist.
  - Restart Home Assistant. Our integration exposes `/static/icons/brands/siegenia/` to serve those local PNGs so the UI shows them immediately.

- Quick local-only placeholder (do not commit):
  - Drop any temporary PNGs into `build/brand/` as `icon.png` (256×256) and `logo.png` (512×256). This is for your dev instance only; do not commit third‑party logos you don’t own.

Once the official brands PR is merged, you can remove any local placeholder assets; Home Assistant will fetch the official ones.

## FAQ

- Q: Can we point to another brand’s icon as a stopgap?
  - A: Don’t submit a PR with someone else’s brand or the HA logo. For local testing, you may place temporary images in `build/brand/`, but don’t commit or distribute them.

- Q: Do we need `brands/*.json` entries?
  - A: Not for a straightforward custom integration brand. Usually just the images in `custom_integrations/siegenia/` are sufficient.

## After Merge

- Verify the Integrations page shows the Siegenia brand for the `siegenia` domain.
- If we added any temporary code or local assets to serve PNGs, we can remove them once the official assets are live.

