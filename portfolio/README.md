# Sivani — Craft in Motion

A scroll-driven UI/UX portfolio hero, built as a single `index.html` with three.js. A ribbon of live recordings of my own websites spirals through 3D space. Then six of them land in a 3×2 grid, and clicking a card opens that live site in a new tab.

## Work shown

| # | Card | Live site |
|---|------|-----------|
| 1 | STRIDE — Brand Story | https://sivanianto123-rgb.github.io/Web_designs/stride/ |
| 2 | Monolith — 3D Configurator | https://monolithe-sneaker.web.app |
| 3 | Freightline — Logistics | https://sivanianto123-rgb.github.io/Web_designs/logistics-freight-hero/ |
| 4 | Bookfeed — Scroll Reader | https://epubfeed.vercel.app |
| 5 | Daily UI — Flutter Screens | https://sivanianto123-rgb.github.io/flutter_ui/ |
| 6 | Flutter Portfolio | https://sivanianto123-rgb.github.io/flutter_protfolio/ |
| 7 | Developer Portfolio (ribbon only) | https://sivanianto123-rgb.github.io/Sd_portfolio/ |
| 8 | Daily UI Vol. 2 (ribbon only) | https://sivanianto123-rgb.github.io/flutter_ui/ |

The `media/*.mp4` files are scroll-through recordings of those sites, at 960 px wide in H.264 (about 5 MB in total).

To change the order, a title or a link, edit the `WORK` array at the top of the `<script>` in `index.html`. The first six entries land in the grid.

## Deploy on Vercel

1. Push this repo to GitHub, if it isn't there already.
2. In Vercel, go to **Add New → Project** and import the repo.
3. Set **Root Directory** to `portfolio`. Set **Framework Preset** to **Other** and leave the build command empty.
4. Click Deploy.

## Preview locally

```bash
python3 -m http.server 8000 -d portfolio
```

Then open http://localhost:8000. A server is needed because browsers won't load the videos into WebGL from `file://`.
