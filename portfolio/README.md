# Portfolio

Single-page portfolio for Sivani T. — merges the content of the two earlier
portfolio sites (`flutter_protfolio` and `Sd_portfolio`) into one site, with:

- A scroll-scrubbed video hero (the uploaded clip, tied to scroll position —
  same technique as `flutter_protfolio/alt-design`).
- Full-viewport sections with soft scroll-snap for a "swipe between sections"
  feel, plus a dot-nav and reveal-on-scroll animations.
- A unified **Work** section covering both Flutter/mobile projects and the
  from-scratch backend systems in this repo (`modelwatch`, `vecsearch`,
  `raftsim`, `repodoc`, `txnkv`), with an All / Flutter & Mobile / Systems &
  AI filter.
- Clicking a project card opens its real result (captured screenshot,
  benchmark chart, etc.) in a modal — a bottom sheet on mobile, swipe down to
  dismiss — nothing is shown until the card is clicked.

No build step: it's plain HTML/CSS/JS (`index.html` + `script.js`) plus
static assets under `assets/`.

## Run locally

```sh
cd portfolio
python3 -m http.server 8000
# open http://localhost:8000
```

## Deploy

`.github/workflows/deploy-portfolio.yml` deploys this folder to GitHub Pages
on every push to `main` that touches `portfolio/**`. Enable it once under
**Settings → Pages → Source → GitHub Actions** on the `workspace` repo; the
site then publishes to `https://sivanianto123-rgb.github.io/workspace/`.

To host it at a bare custom domain or its own `username.github.io` repo
instead, copy `portfolio/`'s contents to the root of that repo and enable
Pages there — no code changes needed.

## Editing content

All copy — skills, experience, and the project list — lives in one place:
the top of `script.js` (`SKILLS`, `EXPERIENCE`, `PROJECTS`). Project images
live in `assets/img/`; the hero video is `assets/video/hero.mp4`.

## Tech-stack logos

`assets/icons/stack/*.svg` are recolored icons from the
[simple-icons](https://simpleicons.org) package (CC0-1.0 — public domain, no
attribution required), pulled locally rather than from a CDN so the site has
no runtime third-party dependency. `TECH_ICONS` in `script.js` maps a skill
or tag's exact name (case-insensitive) to one of these files; any name
without an entry just renders as plain text, so new skills/tags work without
a logo until one is added. To add a logo: drop an SVG at
`assets/icons/stack/<slug>.svg` with its path(s) given an explicit `fill`
color, then add `"name": "<slug>"` to `TECH_ICONS`.
