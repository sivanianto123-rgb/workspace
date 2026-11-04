# Motion Design Portfolio

A one-page portfolio site for a motion designer. It has a showreel, a project grid with case studies, an About section and Contact. It's plain HTML, CSS and JS, so there's no build step.

## Make it yours (about 15 minutes)

All your content goes in **`content.js`**:

1. **Name, role, email, socials.** Replace the placeholders at the top.
2. **Showreel.** Paste a Vimeo or YouTube link into `showreel`, or drop an MP4 in `assets/videos/` and use `"assets/videos/reel.mp4"`.
3. **Projects.** For each one:
   - `preview` is a short, silent, looping MP4 (3–6s, under 3 MB) that plays when someone hovers over the card.
   - `video` is the full piece (a Vimeo or YouTube link is best).
   - `images` are storyboards, style frames and screenshots of your process. Put them in `assets/images/`.
   - Fill in `brief`, `role`, `process` and `tools`. This text is what turns a video into a case study.
   - Until you add a `preview`, the card shows an animated placeholder (`style`: orbit, type, bars, blob, grid or wave).
4. **Accent colour.** Change `--accent` at the top of `styles.css`.
5. **Headline.** Change "Things that move." in `index.html` (look for `data-kinetic`).

## Preview locally

```bash
cd motion-portfolio
python3 -m http.server 8000
```

Then open http://localhost:8000.

## Publish for free

- **Netlify Drop:** drag the `motion-portfolio` folder onto https://app.netlify.com/drop
- **GitHub Pages:** push the folder to a repo, then go to Settings → Pages → deploy from branch
- **Vercel:** import the repo and set the root directory to `motion-portfolio`

## Tips for video files

- Export hover previews as H.264 MP4 at 720p with no audio. Compress them with HandBrake.
- Host full-length videos on Vimeo and link them here. Don't commit large files.
