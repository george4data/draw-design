# Export

Export is **manual only**: run it when the user asks for a PNG, SVG, PDF or an editable image. Never export unprompted.

```bash
<skill-dir>/bin/ddraw export <file>.drawio --format png|svg|pdf|jpg|drawio.png|drawio.svg [--scale 2] [--page N] [--all-pages] [--opaque] [-o out]
```

| Destination | Format | Scale |
|---|---|---|
| README, docs site, wiki | `png` (or `drawio.svg` to keep it editable in the repo) | 2 |
| Slides | `png` | 2 |
| Print / PDF handout | `pdf` (or `png` at 3) | — |
| Figma / Illustrator / further editing | `svg` | — |
| GitHub README that stays editable | `drawio.svg` (opens in the VS Code draw.io extension) | — |

- Uses draw.io Desktop's command line. If it is missing, the command exits 3 with install instructions (`ddraw doctor` explains).
- `--scale` must be within 1–4. For an exact pixel width use `scale = target_width / frame_width` (frame widths: 960 doc-inline, 1280 doc-wide/slide). Below 1 or above 4, redraw at another size preset instead.
- PNG and SVG are transparent by default; `--opaque` keeps the paper background.
- Diagrams have one light palette. Exports always render it as drawn, even when draw.io itself is in dark mode. There is no dark export.
- SVG exports get `<title>`, `<desc>` and `role="img"` from the diagram's title and description. Library images (e.g. Azure icons) are embedded, so the SVG works on any machine.
- Output goes next to the source (`name.png`). An existing file is never overwritten unless you pass `-o`; otherwise `name-1.png` is used.
- Fonts: draw.io Desktop renders with locally installed fonts. If the theme's fonts (Instrument Serif, Geist, Geist Mono) are not installed, exports substitute the fallbacks. `ddraw doctor` reports this.
