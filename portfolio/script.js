(function () {
  "use strict";

  /* ================= DATA ================= */

  // Logos are bundled locally (assets/icons/stack/<slug>.svg, pulled from the
  // simple-icons package) and looked up by this name -> slug map wherever a
  // skill pill, marquee entry or project tag matches a real product/tool
  // name. Phrases that aren't a named product (e.g. "System Design", "Prompt
  // Engineering") have no logo and just render as plain text, same as before.
  var TECH_ICONS = {
    "flutter": "flutter", "dart": "dart", "react": "react", "react.js": "react",
    "next.js": "nextdotjs", "typescript": "typescript", "javascript": "javascript",
    "html5": "html5", "css3": "css3", "figma": "figma", "python": "python",
    "flask": "flask", "graphql": "graphql", "node.js": "nodedotjs", "express": "express",
    "postgresql": "postgresql", "mysql": "mysql", "git": "git", "github": "github",
    "pytest": "pytest", "linux": "linux", "bash": "gnubash", "firebase": "firebase",
    "numpy": "numpy", "chart.js": "chartdotjs", "scikit-learn": "scikitlearn",
    "sqlalchemy": "sqlalchemy",
  };
  function iconFor(name) {
    var slug = TECH_ICONS[String(name).toLowerCase()];
    return slug ? "assets/icons/stack/" + slug + ".svg" : null;
  }
  function techLabel(name, extraClass) {
    var icon = iconFor(name);
    var cls = "tech-label" + (extraClass ? " " + extraClass : "");
    if (!icon) return '<span class="' + cls + '">' + name + "</span>";
    return (
      '<span class="' + cls + ' has-icon">' +
      '<img class="tech-icon" src="' + icon + '" alt="" loading="lazy" width="16" height="16">' +
      "<span>" + name + "</span></span>"
    );
  }

  var SKILLS = [
    { group: "Frontend", items: ["Flutter", "Dart", "React.js", "Next.js", "TypeScript", "JavaScript", "HTML5", "CSS3", "Figma"] },
    { group: "Backend & APIs", items: ["Python", "Flask", "RESTful APIs", "GraphQL", "Node.js", "Express", "Microservices"] },
    { group: "Databases", items: ["PostgreSQL", "MySQL", "PL/SQL", "Relational Schema Design"] },
    { group: "AI / ML Systems", items: ["Prompt Engineering", "Structured Outputs", "Vector Search (HNSW, ANN)", "ML Model Monitoring", "Drift Detection (PSI, KS)"] },
    { group: "Architecture & Tools", items: ["System Design", "Distributed Systems", "Git", "GitHub", "PR Reviews", "Pytest", "Linux", "Bash"] },
  ];

  var SKILL_MARQUEE = [
    "Flutter", "React", "Next.js", "TypeScript", "Python", "Flask", "GraphQL",
    "PostgreSQL", "MySQL", "HNSW", "Raft", "MVCC", "System Design", "Pytest",
    "Node.js", "Prompt Engineering", "Drift Detection", "Figma",
  ];

  var EXPERIENCE = [
    {
      role: "Software / Flutter &amp; Front-End Developer",
      org: "Coreillustrio &middot; Chennai, India",
      dates: "Jun 2025 — Present",
      points: [
        "Shipped a cross-platform (iOS, Android, Web) Flutter phonics-learning app for early-childhood users, owning feature development across a modular, data-driven screen and widget architecture.",
        "Built a real-time speech-recognition feature with a custom lenient-matching engine — syllable, phonetic, and partial-word comparisons — so young children get accurate feedback despite imperfect pronunciation.",
        "Root-caused and fixed a native iOS bug where speech recognition and audio playback conflicted over the AVAudioSession; redesigned the interaction into a sequential play-then-listen state machine with runtime permissions.",
        "Designed an animated feedback system (Lottie/dotlottie) around a multi-emotion mascot, and converted Figma designs into pixel-perfect, responsive UI, integrating REST/GraphQL APIs in an agile, PR-review workflow.",
      ],
    },
    {
      role: "Data Analyst Intern",
      org: "Larsen &amp; Toubro &middot; Chennai, India",
      dates: "Jun 2023 — Jul 2023",
      points: [
        "Designed and normalized relational database schemas using MySQL Workbench, resolving data inconsistencies and optimizing query structure for enterprise datasets.",
        "Presented database normalization concepts and relational data-modeling solutions to engineering leadership.",
      ],
    },
  ];

  var REPO = "https://github.com/sivanianto123-rgb/workspace";
  var IMG = "assets/img/";

  var PROJECTS = [
    {
      id: "phonics",
      category: "flutter",
      index: "01",
      name: "Phonics, made playful.",
      tagline: "Production app &middot; Coreillustrio",
      resultLabel: "Shipped product",
      image: null,
      icon: "✎",
      description:
        "A cross-platform Flutter app that teaches early readers with real-time speech recognition, lenient phonetic matching, and an animated Lottie mascot that reacts to a child's performance.",
      highlights: [
        "Real-time speech_to_text with a custom lenient-matching engine for imperfect child pronunciation",
        "Sequential play-then-listen state machine — fixed a native iOS AVAudioSession conflict",
        "Multi-emotion Lottie mascot, driven by a modular, data-driven screen architecture",
      ],
      tags: ["Flutter", "speech_to_text", "Lottie", "GraphQL"],
      links: {},
    },
    {
      id: "dailyui",
      category: "flutter",
      index: "02",
      name: "Daily UI, rebuilt for practice.",
      tagline: "Ongoing &middot; Design practice",
      resultLabel: "Live gallery",
      image: null,
      icon: "◧",
      description:
        "A running gallery of Flutter UI screens designed and rebuilt daily — pixel-perfect layouts, animation practice, and Figma-to-Flutter implementation.",
      highlights: [
        "Daily Figma-to-Flutter screen rebuilds, focused on motion and layout precision",
        "A live, growing catalog of UI patterns and micro-interactions",
      ],
      tags: ["Flutter", "Figma", "UI/UX"],
      links: { live: "https://sivanianto123-rgb.github.io/flutter_ui/" },
    },
    {
      id: "sneaker",
      category: "flutter",
      index: "03",
      name: "An e-commerce experience.",
      tagline: "Monolith &middot; Made-to-order sneakers",
      resultLabel: "Real capture",
      image: IMG + "ecommerce-hero.png",
      description:
        "A Flutter e-commerce app with a live 3D product configurator — spin a sneaker, recolor every panel, and check out — backed by Firebase Auth and Firestore.",
      highlights: [
        "Live 3D sneaker configurator with per-panel recoloring",
        "Firebase Auth + Firestore backing a full cart-and-checkout flow",
        "State managed with Riverpod across a multi-screen shopping experience",
      ],
      tags: ["Flutter", "Firebase", "Riverpod", "3D Configurator"],
      links: { live: "https://monolithe-sneaker.web.app" },
    },
    {
      id: "modelwatch",
      category: "systems",
      index: "04",
      name: "ModelWatch",
      tagline: "ML Drift Detection Platform &middot; 2026",
      resultLabel: "Real capture — dashboard",
      image: IMG + "modelwatch-dashboard.png",
      description:
        "A full-stack platform that simulates production ML traffic and detects real-time feature drift using Population Stability Index (PSI) and Kolmogorov–Smirnov tests implemented from first principles. Trains a model, serves predictions, logs every scored request, and auto-retrains when drift crosses a threshold.",
      highlights: [
        "Flask app factory with blueprinted routes for train / predict / drift / dashboard",
        "PostgreSQL schema tracking experiments, runs, prediction logs & retrain events",
        "PSI and KS tests implemented from scratch, not pulled from a library",
        "Automated retraining triggered when drifted-feature fraction exceeds a threshold",
      ],
      tags: ["Python", "Flask", "PostgreSQL", "SQLAlchemy", "Chart.js", "scikit-learn"],
      links: { source: REPO + "/tree/main/modelwatch", readme: REPO + "/blob/main/modelwatch/README.md" },
    },
    {
      id: "vecsearch",
      category: "systems",
      index: "05",
      name: "HNSW Vector Search",
      tagline: "Approximate Nearest-Neighbour Engine &middot; 2026",
      resultLabel: "Real capture — benchmark",
      image: IMG + "vecsearch-benchmark.png",
      description:
        "A from-scratch implementation of Hierarchical Navigable Small World (HNSW) graphs — the ANN algorithm behind FAISS, Pinecone, Weaviate, Qdrant and pgvector — built from an exact brute-force index through a single-layer NSW graph to the full hierarchical index.",
      highlights: [
        "Benchmarked against brute-force across 50K vectors with measured recall@10 vs. latency",
        "Up to 43x query speedup over brute force at scale, with tunable recall via ef_search",
        "Diversity-heuristic neighbour selection from the original HNSW paper",
        "CLI (vecsearch build | query | benchmark) plus a persistence layer and Pareto chart",
      ],
      tags: ["Python", "NumPy", "Data Structures", "ANN Search", "Pytest"],
      links: { source: REPO + "/tree/main/vecsearch", readme: REPO + "/blob/main/vecsearch/README.md" },
    },
    {
      id: "raftsim",
      category: "systems",
      index: "06",
      name: "raftsim",
      tagline: "Raft Consensus Simulator &middot; 2026",
      resultLabel: "Real capture — failover",
      image: IMG + "raftsim-failover.png",
      description:
        "A dependency-free simulation of the Raft consensus algorithm — leader election, heartbeats, log replication, and crash / network-partition fault injection — running on a single-threaded simulated clock so the whole protocol is a deterministic function of its inputs.",
      highlights: [
        "Interactive REPL: kill / revive nodes, partition & heal the network, submit commands",
        "Automated tests verifying split-brain prevention and automatic leader recovery",
        "Deterministic, seedable simulation — a bug found at tick 2000 reproduces every time",
      ],
      tags: ["Python", "Distributed Systems", "Concurrency"],
      links: { source: REPO + "/tree/main/raftsim", readme: REPO + "/blob/main/raftsim/README.md" },
    },
    {
      id: "repodoc",
      category: "systems",
      index: "07",
      name: "Repo Doctor",
      tagline: "Git Static Analysis CLI &middot; 2026",
      resultLabel: "Real capture — scan",
      image: IMG + "repodoc-scan.png",
      description:
        "A pip-installable CLI that runs pattern-based static analysis over Git repositories to flag leaked secrets, oversized files, and missing .gitignore entries — with color-coded terminal reporting, built to work as a pre-commit gate.",
      highlights: [
        "Detects AWS keys, generic API keys, hardcoded passwords & private-key blocks",
        "Shipped with a full pytest suite validating every check against fixture repos",
        "Proper exit codes (0 / 1 / 2) so it drops straight into a pre-commit hook",
      ],
      tags: ["Python", "Pytest", "Static Analysis", "Git"],
      links: { source: REPO + "/tree/main/repodoc", readme: REPO + "/blob/main/repodoc/README.md" },
    },
    {
      id: "txnkv",
      category: "systems",
      index: "08",
      name: "txnkv",
      tagline: "WAL + MVCC Transaction Engine &middot; 2026",
      resultLabel: "Real capture — isolation",
      image: IMG + "txnkv-isolation.png",
      description:
        "A transactional key-value store built from two ideas every real database relies on: a write-ahead log for crash-safe durability, and multi-version concurrency control for snapshot-isolated reads with write-write conflict detection.",
      highlights: [
        "fsync-on-every-append WAL; state rebuilds correctly from the log alone after a crash",
        "Snapshot isolation verified by test: a long-running transaction never sees a later commit",
        '"First committer wins" conflict detection with ConflictError on write-write races',
      ],
      tags: ["Python", "SQL", "Storage Engines", "System Design"],
      links: { source: REPO + "/tree/main/txnkv", readme: REPO + "/blob/main/txnkv/README.md" },
    },
  ];

  var SECTIONS = ["about", "skills", "experience", "work", "contact"];

  /* ================= RENDER ================= */

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function renderSkills() {
    var wrap = document.getElementById("skillGroups");
    SKILLS.forEach(function (g, i) {
      var card = el("div", "skill-card reveal" + (i % 2 ? " d1" : ""));
      card.appendChild(el("h4", null, g.group));
      var pills = el("div", "skill-pills");
      g.items.forEach(function (s) {
        pills.insertAdjacentHTML("beforeend", techLabel(s, "skill-pill"));
      });
      card.appendChild(pills);
      wrap.appendChild(card);
    });

    var track = document.getElementById("marqueeTrack");
    var html = SKILL_MARQUEE.map(function (s) {
      return '<span class="marquee-item">' + techLabel(s) + " <i>&#10022;</i></span>";
    }).join("");
    track.innerHTML = html + html; // duplicate for seamless loop
  }

  function renderExperience() {
    var wrap = document.getElementById("timeline");
    EXPERIENCE.forEach(function (x, i) {
      var item = el("div", "tl-item reveal" + (i ? " d1" : ""));
      var when = el("div", "tl-when", x.dates);
      var body = el("div");
      body.appendChild(el("h3", "tl-role", x.role));
      body.appendChild(el("p", "tl-org", x.org));
      var pts = el("ul", "tl-points");
      x.points.forEach(function (p) { pts.appendChild(el("li", null, p)); });
      body.appendChild(pts);
      item.appendChild(when);
      item.appendChild(body);
      wrap.appendChild(item);
    });
  }

  function renderProjects() {
    var grid = document.getElementById("projGrid");
    PROJECTS.forEach(function (p, i) {
      var card = el("article", "proj-card reveal" + (i % 3 ? " d" + ((i % 3)) : ""));
      card.setAttribute("data-cat", p.category);
      card.setAttribute("data-id", p.id);
      card.innerHTML =
        '<div class="proj-top">' +
          '<span class="proj-index">' + p.index + "</span>" +
          '<span class="proj-cat">' + (p.category === "flutter" ? "Flutter / Mobile" : "Systems / AI") + "</span>" +
        "</div>" +
        '<h3 class="proj-name">' + p.name + "</h3>" +
        '<p class="proj-tagline">' + p.tagline + "</p>" +
        '<div class="proj-foot">' +
          '<div class="proj-tags">' + p.tags.slice(0, 2).map(function (t) { return techLabel(t); }).join("") + "</div>" +
          '<span class="proj-view">View result <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M13 6l6 6-6 6"/></svg></span>' +
        "</div>";
      card.addEventListener("click", function () { openModal(p); });
      card.addEventListener("mousemove", function (e) {
        var r = card.getBoundingClientRect();
        card.style.setProperty("--mx", ((e.clientX - r.left) / r.width) * 100 + "%");
        card.style.setProperty("--my", ((e.clientY - r.top) / r.height) * 100 + "%");
      });
      grid.appendChild(card);
    });
  }

  /* ================= PROJECT MODAL ================= */

  var backdrop = document.getElementById("modalBackdrop");
  var modal = document.getElementById("modal");
  var modalMedia = document.getElementById("modalMedia");
  var modalEyebrow = document.getElementById("modalEyebrow");
  var modalTitle = document.getElementById("modalTitle");
  var modalDesc = document.getElementById("modalDesc");
  var modalHighlights = document.getElementById("modalHighlights");
  var modalTags = document.getElementById("modalTags");
  var modalLinks = document.getElementById("modalLinks");
  var modalClose = document.getElementById("modalClose");

  function openModal(p) {
    if (p.image) {
      modalMedia.className = "modal-media";
      modalMedia.innerHTML = '<img src="' + p.image + '" alt="' + p.name + ' — result">';
    } else {
      modalMedia.className = "modal-media placeholder";
      modalMedia.innerHTML = "<span>" + (p.icon || "◆") + "</span>";
    }
    modalMedia.innerHTML += '<span class="modal-result-tag">' + p.resultLabel + "</span>";

    modalEyebrow.textContent = p.index + " — " + (p.category === "flutter" ? "Flutter / Mobile" : "Systems / AI");
    modalTitle.textContent = p.name;
    modalDesc.textContent = p.description;

    modalHighlights.innerHTML = "";
    p.highlights.forEach(function (h) { modalHighlights.appendChild(el("li", null, h)); });

    modalTags.innerHTML = p.tags.map(function (t) { return techLabel(t); }).join("");

    modalLinks.innerHTML = "";
    var linkMap = { source: "Source &rarr;", readme: "Read-me &rarr;", live: "Live site &rarr;" };
    Object.keys(linkMap).forEach(function (k) {
      if (p.links && p.links[k]) {
        var a = el("a", "pill" + (k === "live" ? "" : " ghost"), linkMap[k]);
        a.href = p.links[k];
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        modalLinks.appendChild(a);
      }
    });
    if (!p.links || (!p.links.source && !p.links.readme && !p.links.live)) {
      modalLinks.appendChild(el("span", null, '<span style="font-size:13px;color:var(--fg-faint);">Private / internal product — no public source.</span>'));
    }

    backdrop.classList.add("open");
    modal.classList.add("open");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    backdrop.classList.remove("open");
    modal.classList.remove("open");
    document.body.style.overflow = "";
  }

  backdrop.addEventListener("click", closeModal);
  modalClose.addEventListener("click", closeModal);
  window.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeModal();
  });

  // swipe-down to dismiss on mobile bottom-sheet
  (function () {
    var startY = null, dy = 0, dragging = false;
    modal.addEventListener("touchstart", function (e) {
      if (window.innerWidth > 720) return;
      if (modal.scrollTop > 0) return;
      startY = e.touches[0].clientY;
      dragging = true;
    }, { passive: true });
    modal.addEventListener("touchmove", function (e) {
      if (!dragging || startY === null) return;
      dy = e.touches[0].clientY - startY;
      if (dy > 0) modal.style.transform = "translateY(" + dy + "px)";
    }, { passive: true });
    modal.addEventListener("touchend", function () {
      if (!dragging) return;
      dragging = false;
      if (dy > 110) {
        closeModal();
      }
      modal.style.transform = "";
      startY = null; dy = 0;
    });
  })();

  /* ================= FILTER ================= */

  document.querySelectorAll(".filter-row button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".filter-row button").forEach(function (b) { b.classList.remove("active"); });
      btn.classList.add("active");
      var f = btn.getAttribute("data-filter");
      document.querySelectorAll(".proj-card").forEach(function (card) {
        card.hidden = f !== "all" && card.getAttribute("data-cat") !== f;
      });
    });
  });

  /* ================= NAV / JUMP ================= */

  function jump(id) {
    var target = document.getElementById(id);
    if (!target) return;
    var top = target.getBoundingClientRect().top + window.pageYOffset - 70;
    window.scrollTo({ top: top, behavior: "smooth" });
    closeMobileMenu();
  }

  document.querySelectorAll("[data-jump]").forEach(function (n) {
    n.addEventListener("click", function (e) {
      e.preventDefault();
      jump(n.getAttribute("data-jump"));
    });
  });

  var mobileMenu = document.getElementById("mobileMenu");
  var burger = document.getElementById("burger");
  function closeMobileMenu() { mobileMenu.classList.remove("open"); }
  burger.addEventListener("click", function () { mobileMenu.classList.toggle("open"); });

  /* ================= DOT NAV ================= */

  var dotNav = document.getElementById("dotNav");
  var dotBtns = {};
  SECTIONS.forEach(function (id) {
    var b = el("button");
    b.setAttribute("aria-label", id);
    b.addEventListener("click", function () { jump(id); });
    dotNav.appendChild(b);
    dotBtns[id] = b;
  });

  /* ================= REVEAL ON SCROLL ================= */

  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (ent) {
      if (ent.isIntersecting) ent.target.classList.add("in");
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -8% 0px" });

  function observeReveals() {
    document.querySelectorAll(".reveal").forEach(function (n) { io.observe(n); });
  }

  var sectionIO = new IntersectionObserver(function (entries) {
    entries.forEach(function (ent) {
      var id = ent.target.id;
      if (ent.isIntersecting) {
        Object.keys(dotBtns).forEach(function (k) { dotBtns[k].classList.toggle("active", k === id); });
        document.querySelectorAll(".navlink").forEach(function (n) {
          n.classList.toggle("active", n.getAttribute("data-jump") === id);
        });
      }
    });
  }, { threshold: 0.45 });

  /* ================= CHROME SOLID ON SCROLL ================= */

  var chrome = document.getElementById("chrome");
  var scrollCue = document.getElementById("scrollCue");
  function onScrollChrome() {
    var sc = window.pageYOffset > 40;
    chrome.classList.toggle("solid", sc);
    scrollCue.style.opacity = window.pageYOffset > 120 ? "0" : "1";
  }
  window.addEventListener("scroll", onScrollChrome, { passive: true });

  /* ================= VIDEO SCROLL-SCRUB (hero) ================= */

  (function () {
    var VIDEO_URL = "assets/video/hero.mp4";
    var clip = document.getElementById("clip");
    var boot = document.getElementById("boot");
    var bootBar = document.getElementById("bootBar");
    var bootPct = document.getElementById("bootPct");
    var meter = document.getElementById("meter");
    var panels = Array.prototype.slice.call(document.querySelectorAll("[data-panel]"));
    var track = document.querySelector(".track");
    var contentVeil = document.getElementById("contentVeil");

    // Frame-checked against hero.mp4's actual 10s runtime (progress * duration
    // = video currentTime): clean portrait+swirl 0-2.0s, UI/app mockups
    // 3.3-4.0s, neural-network graphic 4.6-6.8s, colourful "range" ribbons
    // 7.0-8.3s, back to portrait 9.0-10s, with cross-fades between. Each
    // panel's dwell window sits inside its beat's clean footage, and fades
    // ride the video's own cross-fade into the next beat — the copy narrates
    // exactly what's on screen underneath it.
    var CUES = [
      [0.00, 0.00, 0.16, 0.21],
      [0.23, 0.28, 0.40, 0.45],
      [0.47, 0.52, 0.66, 0.70],
      [0.71, 0.75, 0.86, 0.90],
      [0.91, 0.95, 0.97, 1.00],
    ];
    var DRIFT = 20;
    var FPS = 24;
    var FOLLOW_MS = 55;

    function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
    function smooth(t) { return t * t * (3 - 2 * t); }
    function ramp(p, a, b) {
      if (b <= a) return p >= b ? 1 : 0;
      return smooth(clamp((p - a) / (b - a), 0, 1));
    }

    var progress = 0, seekTo = 0, seekAt = 0, duration = 0, ready = false;

    // Once the visitor scrolls past the hero track, the video stays as a
    // fixed background behind every section (About, Skills, Experience,
    // Work, Contact) instead of disappearing behind a solid panel — it just
    // switches from scroll-scrubbing to a free-running loop, since there's
    // no more "story" left to scrub through. Scrolling back up into the
    // hero hands control back to the scrub.
    var ambient = false;
    function updateAmbient() {
      var trackEnd = track.offsetHeight - window.innerHeight;
      var pastHero = trackEnd <= 0 ? window.pageYOffset > 10 : window.pageYOffset >= trackEnd - 2;
      if (pastHero && !ambient) {
        ambient = true;
        clip.loop = true;
        var p = clip.play();
        if (p && p.catch) p.catch(function () {});
      } else if (!pastHero && ambient) {
        ambient = false;
        clip.loop = false;
        clip.pause();
        seekAt = seekTo;
        shownFrame = Math.round(seekAt * FPS);
        try { clip.currentTime = seekAt; } catch (e) {}
      }
    }

    // Keeps the fixed video dimmed-but-visible behind the hero, then ramps
    // a dark veil in as the hero track ends so the About/Skills/Experience/
    // Work/Contact copy stays legible over whatever the loop is showing.
    function updateVeil() {
      var trackEnd = track.offsetHeight - window.innerHeight;
      var y = window.pageYOffset;
      var v;
      if (trackEnd <= 0) {
        v = y > 10 ? 1 : 0;
      } else {
        var startY = trackEnd * 0.88;
        var endY = trackEnd + window.innerHeight * 0.4;
        v = clamp((y - startY) / (endY - startY), 0, 1);
      }
      contentVeil.style.opacity = v;
    }

    function trackProgress() {
      var max = track.offsetHeight - window.innerHeight;
      var y = window.pageYOffset;
      progress = max > 0 ? clamp(y / max, 0, 1) : (y > 10 ? 1 : 0);
      if (duration) seekTo = progress * duration;
      updateAmbient();
      updateVeil();
    }

    var painted = -1;
    function paint() {
      if (progress === painted) return;
      painted = progress;
      meter.style.transform = "scaleX(" + progress + ")";
      for (var i = 0; i < panels.length; i++) {
        var c = CUES[i];
        var enter = ramp(progress, c[0], c[1]);
        var leave = ramp(progress, c[2], c[3]);
        var o = enter * (1 - leave);
        var y = (1 - enter) * DRIFT - leave * DRIFT;
        panels[i].style.opacity = o;
        panels[i].style.transform = "translate3d(0," + y + "px,0)";
        panels[i].style.pointerEvents = o > 0.6 ? "auto" : "none";
      }
      // fade whole fixed stage out once we're well past the hero track
      var stageOpacity = progress >= 1 ? clamp(1 - (window.pageYOffset - track.offsetHeight + window.innerHeight) / (window.innerHeight * 0.6), 0, 1) : 1;
    }

    var shownFrame = -1, lastNow = 0;
    function frame(now) {
      var dt = lastNow ? Math.min(now - lastNow, 100) : 16.7;
      lastNow = now;
      if (ready && duration && !ambient) {
        var gap = seekTo - seekAt;
        if (Math.abs(gap) > 0.0008) {
          seekAt = Math.abs(gap) < 0.25 / FPS ? seekTo : seekAt + gap * (1 - Math.exp(-dt / FOLLOW_MS));
        }
        var f = Math.round(seekAt * FPS);
        if (f !== shownFrame && clip.readyState >= 2 && !clip.seeking) {
          shownFrame = f;
          try { clip.currentTime = Math.min(f / FPS, duration); } catch (e) {}
        }
      }
      paint();
      requestAnimationFrame(frame);
    }

    function setProgress(f) {
      bootBar.style.transform = "scaleX(" + f + ")";
      bootPct.textContent = "Loading " + Math.round(f * 100) + "%";
    }

    var started = false;
    function start() {
      if (started) return;
      started = true;
      ready = true;
      boot.classList.add("done");
      document.documentElement.classList.add("has-snap");
      trackProgress();
      seekAt = seekTo;
      observeReveals();
      SECTIONS.forEach(function (id) {
        var node = document.getElementById(id);
        if (node) sectionIO.observe(node);
      });
    }

    var attached = false;
    function attach(src) {
      if (attached) return;
      attached = true;
      clip.addEventListener("loadedmetadata", function () {
        duration = clip.duration || 0;
        clip.pause();
        trackProgress();
        seekAt = seekTo;
        shownFrame = Math.round(seekAt * FPS);
        try { clip.currentTime = seekAt; } catch (e) {}
      });
      clip.addEventListener("loadeddata", start);
      clip.addEventListener("canplaythrough", start);
      clip.addEventListener("error", start);
      clip.src = src;
      clip.load();
      setTimeout(start, 9000);
    }

    function preload() {
      var ctrl = typeof AbortController !== "undefined" ? new AbortController() : null;
      var bail = setTimeout(function () {
        if (attached) return;
        if (ctrl) ctrl.abort();
        setProgress(1);
        attach(VIDEO_URL);
      }, 12000);

      fetch(VIDEO_URL, { signal: ctrl ? ctrl.signal : undefined })
        .then(function (res) {
          if (!res.ok || !res.body) throw new Error("fetch failed");
          var total = parseInt(res.headers.get("content-length"), 10) || 0;
          var reader = res.body.getReader();
          var chunks = [];
          var got = 0;
          return new Promise(function (resolve, reject) {
            function pump() {
              reader.read().then(function (r) {
                if (r.done) {
                  resolve(new Blob(chunks, { type: "video/mp4" }));
                  return;
                }
                chunks.push(r.value);
                got += r.value.length;
                setProgress(total ? got / total : Math.min(got / 5e6, 0.95));
                pump();
              }).catch(reject);
            }
            pump();
          });
        })
        .then(function (blob) {
          clearTimeout(bail);
          setProgress(1);
          attach(URL.createObjectURL(blob));
        })
        .catch(function () {
          clearTimeout(bail);
          setProgress(1);
          attach(VIDEO_URL);
        });
    }

    function unlock() {
      var p = clip.play();
      if (p && p.then) p.then(function () { clip.pause(); }).catch(function () {});
      else clip.pause();
    }
    ["touchstart", "pointerdown", "wheel", "keydown"].forEach(function (ev) {
      window.addEventListener(ev, unlock, { once: true, passive: true });
    });

    window.addEventListener("scroll", trackProgress, { passive: true });
    window.addEventListener("resize", trackProgress);

    trackProgress();
    paint();
    preload();
    requestAnimationFrame(frame);

    // Fallback: if something goes wrong with IO above start(), still wire reveals.
    setTimeout(function () {
      if (!started) start();
    }, 13000);
  })();

  /* ================= INIT ================= */

  renderSkills();
  renderExperience();
  renderProjects();
  document.getElementById("year").textContent = new Date().getFullYear();
})();
