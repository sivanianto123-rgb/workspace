(() => {
  const P = window.PORTFOLIO;
  const $ = (s, el = document) => el.querySelector(s);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const esc = (s = "") => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ---------- basic content ---------- */
  document.title = `${P.name} — ${P.role}`;
  document.querySelectorAll("[data-name]").forEach(el => (el.textContent = P.name));
  document.querySelectorAll("[data-role]").forEach(el => (el.textContent = P.role));
  document.querySelectorAll("[data-location]").forEach(el => (el.textContent = P.location));
  $("[data-tagline]").textContent = P.tagline;
  $("#year").textContent = new Date().getFullYear();

  const email = $("#email-link");
  email.href = `mailto:${P.email}`;
  email.textContent = P.email;

  $("#about-text").innerHTML = P.about.map(p => `<p>${esc(p)}</p>`).join("");
  $("#tools").innerHTML = P.tools.map(t => `<li>${esc(t)}</li>`).join("");
  $("#skills").innerHTML = P.skills.map(t => `<li>${esc(t)}</li>`).join("");
  $("#socials").innerHTML = P.socials.map(s => `<li><a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label)} ↗</a></li>`).join("");
  if (P.cv) { const cv = $("#cv-link"); cv.href = P.cv; cv.hidden = false; }

  const words = [...P.skills, P.role];
  $("#marquee").innerHTML = [...words, ...words].map(w => `<span>${esc(w)} ✦</span>`).join("");

  /* ---------- kinetic headline: split into chars ---------- */
  const h1 = $("[data-kinetic]");
  let i = 0;
  h1.innerHTML = h1.innerHTML.split(/<br\s*\/?>/).map((line, li, arr) =>
    line.trim().split(" ").map(word => {
      const isLast = li === arr.length - 1;
      return `<span class="word${isLast ? " accent" : ""}">${[...word].map(ch =>
        `<span class="char" style="animation-delay:${0.15 + i++ * 0.045}s">${ch}</span>`).join("")}</span>`;
    }).join(" ")
  ).join("<br>");

  /* ---------- placeholder motion thumbnails ---------- */
  const placeholder = (style, color, title = "") => {
    const n = { orbit: 3, bars: 5, grid: 18, wave: 14 }[style] || 0;
    let inner = "";
    if (style === "type") inner = [...(title.replace(/[^A-Za-z]/g, "").slice(0, 4).toUpperCase() || "MOVE")].map(c => `<span>${c}</span>`).join("");
    else if (style === "grid") inner = Array.from({ length: n }, (_, k) => `<i style="animation-delay:${((k % 6) + Math.floor(k / 6)) * 0.12}s"></i>`).join("");
    else if (style === "wave") inner = Array.from({ length: n }, (_, k) => `<i style="animation-delay:${k * 0.08}s"></i>`).join("");
    else inner = "<i></i>".repeat(n);
    return `<div class="ph ph-${style}" style="--c:${color}">${inner}</div>`;
  };

  /* ---------- project grid ---------- */
  const grid = $("#project-grid");
  grid.innerHTML = P.projects.map((p, idx) => `
    <button class="card reveal" data-idx="${idx}" style="transition-delay:${(idx % 2) * 0.12}s">
      <div class="card-media">
        ${p.preview
          ? `<video src="${esc(p.preview)}" muted loop playsinline preload="metadata"></video>`
          : placeholder(p.style, p.color, p.title)}
        <span class="card-view">View case study</span>
      </div>
      <div class="card-meta">
        <span class="card-title">${esc(p.title)}</span>
        <span class="card-cat">${esc(p.category)} · ${esc(p.year)}</span>
      </div>
    </button>`).join("");

  grid.querySelectorAll(".card").forEach(card => {
    const v = card.querySelector("video");
    if (v) {
      card.addEventListener("mouseenter", () => v.play().catch(() => {}));
      card.addEventListener("mouseleave", () => { v.pause(); v.currentTime = 0; });
    }
    card.addEventListener("click", () => openProject(P.projects[+card.dataset.idx]));
  });

  /* ---------- video embed helper (Vimeo / YouTube / MP4) ---------- */
  const embed = (url, fallbackHTML) => {
    if (!url) return `<div class="video-frame">${fallbackHTML}</div>`;
    const vimeo = url.match(/vimeo\.com\/(?:video\/)?(\d+)/);
    const yt = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|shorts\/))([\w-]{11})/);
    if (vimeo) return `<div class="video-frame"><iframe src="https://player.vimeo.com/video/${vimeo[1]}?autoplay=1&title=0&byline=0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe></div>`;
    if (yt) return `<div class="video-frame"><iframe src="https://www.youtube-nocookie.com/embed/${yt[1]}?autoplay=1&rel=0" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen></iframe></div>`;
    return `<div class="video-frame"><video src="${esc(url)}" controls autoplay playsinline></video></div>`;
  };

  /* ---------- modal ---------- */
  const modal = $("#modal"), body = $("#modal-body");
  let lastFocus = null;
  const open = html => {
    lastFocus = document.activeElement;
    body.innerHTML = html;
    modal.classList.add("open");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    $(".modal-close", modal).focus();
  };
  const close = () => {
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    setTimeout(() => (body.innerHTML = ""), 400); // stops video playback
    lastFocus && lastFocus.focus();
  };
  modal.addEventListener("click", e => e.target.closest("[data-close]") && close());
  addEventListener("keydown", e => e.key === "Escape" && modal.classList.contains("open") && close());

  $("#play-reel").addEventListener("click", () =>
    open(embed(P.showreel, `${placeholder("blob", "var(--accent)")}<div class="video-empty"><p><strong>Showreel coming soon.</strong><br>Add your Vimeo/YouTube link or MP4 to <code>showreel</code> in content.js.</p></div>`))
  );

  const openProject = p => open(`
    ${embed(p.video, placeholder(p.style, p.color, p.title))}
    <div class="cs-head">
      <p class="eyebrow">${esc(p.category)} · ${esc(p.year)}</p>
      <h3>${esc(p.title)}</h3>
    </div>
    <div class="cs-grid">
      <div><h4>The brief</h4><p>${esc(p.brief)}</p></div>
      <div><h4>My role</h4><p>${esc(p.role)}</p></div>
      <div><h4>Process</h4><p>${esc(p.process)}</p></div>
      <div><h4>Tools</h4><p>${p.tools.map(esc).join(", ")}</p></div>
    </div>
    ${p.images && p.images.length ? `<div class="cs-images">${p.images.map(src => `<img src="${esc(src)}" alt="${esc(p.title)} process image" loading="lazy">`).join("")}</div>` : ""}
  `);

  /* ---------- scroll reveal ---------- */
  const io = new IntersectionObserver(entries => entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
  }), { threshold: 0.15 });
  document.querySelectorAll(".reveal").forEach(el => io.observe(el));

  /* ---------- custom cursor ---------- */
  const cursor = $(".cursor");
  let cx = innerWidth / 2, cy = innerHeight / 2, tx = cx, ty = cy;
  addEventListener("pointermove", e => { tx = e.clientX; ty = e.clientY; });
  document.addEventListener("pointerover", e => cursor.classList.toggle("big", !!e.target.closest("a, button")));
  (function loop() {
    cx += (tx - cx) * 0.2; cy += (ty - cy) * 0.2;
    cursor.style.transform = `translate(${cx}px, ${cy}px) translate(-50%, -50%)`;
    requestAnimationFrame(loop);
  })();

  /* ---------- hero canvas: flowing particle field that reacts to the pointer ---------- */
  const canvas = $("#hero-canvas"), ctx = canvas.getContext("2d");
  const accent = getComputedStyle(document.documentElement).getPropertyValue("--accent").trim();
  let W, H, dots, mouse = { x: -9999, y: -9999 };
  const resize = () => {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = W * dpr; canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const gap = W < 700 ? 34 : 42;
    dots = [];
    for (let y = gap / 2; y < H; y += gap) for (let x = gap / 2; x < W; x += gap) dots.push({ x, y });
  };
  resize();
  addEventListener("resize", resize);
  canvas.parentElement.addEventListener("pointermove", e => {
    const r = canvas.getBoundingClientRect(); mouse.x = e.clientX - r.left; mouse.y = e.clientY - r.top;
  });
  canvas.parentElement.addEventListener("pointerleave", () => (mouse.x = mouse.y = -9999));

  const draw = t => {
    ctx.clearRect(0, 0, W, H);
    for (const d of dots) {
      const wave = Math.sin(d.x * 0.012 + t * 0.0012) * Math.cos(d.y * 0.014 + t * 0.0009);
      const dx = d.x - mouse.x, dy = d.y - mouse.y, dist = Math.hypot(dx, dy);
      const push = Math.max(0, 1 - dist / 180);
      const x = d.x + wave * 8 + (dx / (dist || 1)) * push * 26;
      const y = d.y + wave * 8 + (dy / (dist || 1)) * push * 26;
      const r = 1.1 + (wave + 1) * 0.9 + push * 3;
      ctx.fillStyle = push > 0.05 ? accent : `rgba(244,241,234,${0.08 + (wave + 1) * 0.1})`;
      ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
    }
    if (!reduced) requestAnimationFrame(draw);
  };
  requestAnimationFrame(draw);
})();
