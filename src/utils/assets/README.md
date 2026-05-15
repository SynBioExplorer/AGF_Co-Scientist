# HTML report assets

Drop `AusGenome_LOGO_MAIN.png` (the master 1024+ px PNG, transparent
background) into this directory. It will be base64-inlined into every
generated HTML report by `src/utils/html_report.py` — no external file
dependency at view time.

Lookup order (first hit wins):

1. `src/utils/assets/AusGenome_LOGO_MAIN.png`  ← preferred
2. `<repo_root>/AusGenome_LOGO_MAIN.png`        ← legacy fallback

If neither file exists, or Pillow isn't installed, the brand row degrades
to a text-only "Australian Genome Foundry" label (no broken-image icon).

## Why Pillow?

The logo is resized to 96 px height (≈2-3× retina display) before being
embedded, so the file size stays small (~5–10 KB) without sacrificing
sharpness. Pillow is listed in `requirements-api.txt`.
