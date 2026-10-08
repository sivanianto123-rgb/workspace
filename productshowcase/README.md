# AURA — Product Showcase

A motion-driven product showcase site inspired by [motion.zajno.com](https://motion.zajno.com/):
dark theme, oversized kinetic typography, a custom cursor, infinite marquees,
scroll-triggered reveals and parallax, all built with plain HTML/CSS/JS.

## Stack

- No build step — static HTML/CSS/JS, open `index.html` directly or serve it.
- [GSAP](https://gsap.com/) + ScrollTrigger for scroll-triggered animations and parallax.
- [Lenis](https://github.com/darkroomengineering/lenis) for buttery smooth scrolling.
- GSAP, ScrollTrigger and Lenis are vendored locally under `js/vendor/` (no
  CDN dependency), and the product "photography" is all inline SVG + CSS
  gradients, so the whole site works fully offline.

## Run locally

```bash
cd productshowcase
python3 -m http.server 8000
# open http://localhost:8000
```

## Structure

```
productshowcase/
├── index.html       # markup + content (hero, product grid, spotlight, stats, journal, CTA)
├── css/style.css    # design system: colors, type scale, layout, animations
└── js/main.js       # preloader, cursor, smooth scroll, reveals, counters
```

## Customizing

- Swap the six placeholder products in the `.grid` section of `index.html`
  — each `.card` just needs an SVG icon, title, category and a `card__visual--0N`
  gradient class in `css/style.css`.
- Colors and type live in the `:root` variables at the top of `css/style.css`
  (`--bg`, `--fg`, `--accent`).
- Replace the mailto CTA and social links in the `#contact` section and footer.
