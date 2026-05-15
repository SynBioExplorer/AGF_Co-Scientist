# HTML report assets

`AusGenome_LOGO_MAIN.png` (the master 1024+ px PNG, transparent background)
lives in this directory. It is base64-inlined into every generated HTML
report by `src/utils/html_report.py` — no external file dependency at view
time.

If the file isn't present, or Pillow isn't installed, the brand row degrades
to a text-only "Australian Genome Foundry" label (no broken-image icon).

## Why Pillow?

The logo is resized to 96 px height (≈2-3× retina display) before being
embedded, so the file size stays small (~5–10 KB) without sacrificing
sharpness. Pillow is listed in `requirements-api.txt`.
