/* =========================================================
   EDIT THIS FILE — all of your portfolio content lives here.
   You never need to touch index.html / styles.css / main.js.
   ========================================================= */

window.PORTFOLIO = {
  name: "Your Name",                       // ← your name
  role: "Motion Designer",                 // ← e.g. "Motion Designer & Animator"
  location: "City, Country",
  tagline: "I make brands move — kinetic type, logo animation, explainers and loops that people actually watch.",
  email: "you@example.com",

  // Your showreel. Paste a Vimeo or YouTube link, OR a local file path like "assets/videos/reel.mp4".
  // Leave "" until you have one — the button will show a friendly placeholder.
  showreel: "",

  socials: [
    { label: "Vimeo",     url: "https://vimeo.com/" },
    { label: "Behance",   url: "https://www.behance.net/" },
    { label: "Instagram", url: "https://instagram.com/" },
    { label: "LinkedIn",  url: "https://linkedin.com/" },
  ],

  cv: "",  // e.g. "assets/cv.pdf" — leave "" to hide the button

  about: [
    "I'm a motion designer who loves turning flat ideas into movement. I work across 2D, kinetic typography and light 3D, and I care just as much about the idea as the easing curves.",
    "Currently open to freelance and full-time roles. Let's make something that moves.",
  ],

  tools: ["After Effects", "Premiere Pro", "Illustrator", "Photoshop", "Cinema 4D", "Blender", "Figma"],
  skills: ["Kinetic Typography", "Logo Animation", "Explainers", "Social Content", "UI Motion", "Storyboarding", "Style Frames"],

  /* ---------- PROJECTS ----------
     style   : placeholder animation shown until you add a video
               one of: "orbit" | "type" | "bars" | "blob" | "grid" | "wave"
     preview : short looping MP4 for the card (plays on hover), e.g. "assets/videos/p1-loop.mp4"
     video   : full video — Vimeo/YouTube link or local MP4
     images  : process images (storyboards, style frames…) e.g. ["assets/images/p1-board.jpg"]
  -------------------------------- */
  projects: [
    {
      title: "Kinetic Type — \"Say It Loud\"",
      category: "Kinetic Typography",
      year: "2026",
      color: "#ff5b2e",
      style: "type",
      preview: "", video: "", images: [],
      brief: "A 30-second kinetic typography piece set to a spoken-word clip, exploring rhythm and emphasis through type.",
      role: "Concept, design, animation, sound edit",
      process: "Started with the audio waveform, marked every beat and stressed syllable, then built a type system with three weights that react to volume. Style frames in Illustrator, animation in After Effects with expression-driven scaling.",
      tools: ["After Effects", "Illustrator"],
    },
    {
      title: "Nova Coffee — Logo Reveal",
      category: "Brand Animation",
      year: "2026",
      color: "#ffc93c",
      style: "orbit",
      preview: "", video: "", images: [],
      brief: "A 6-second logo sting for a (fictional) specialty coffee brand, built for social intros and in-store screens.",
      role: "Design & animation",
      process: "Explored 3 directions — liquid, orbital and typographic. The orbital version won: coffee beans circle and collapse into the mark. Delivered in 16:9, 1:1 and 9:16.",
      tools: ["After Effects", "Illustrator"],
    },
    {
      title: "Pocket Bank — App Explainer",
      category: "Explainer",
      year: "2025",
      color: "#3ce0ff",
      style: "bars",
      preview: "", video: "", images: [],
      brief: "A 45-second explainer showing how a budgeting app helps you save without thinking about it.",
      role: "Script, storyboard, illustration, animation",
      process: "Wrote the script around a single character's month. Storyboarded 18 frames, designed a flat illustration style, and used UI animation to show features without screen recordings.",
      tools: ["After Effects", "Illustrator", "Figma"],
    },
    {
      title: "Loops Vol. 1",
      category: "Personal / 3D",
      year: "2025",
      color: "#b06bff",
      style: "blob",
      preview: "", video: "", images: [],
      brief: "A series of seamless 3D loops made as daily practice — materials, lighting and satisfying motion.",
      role: "Everything",
      process: "One loop a day for 10 days. Each one focused on a single idea: soft bodies, cloth, glass, displacement. Rendered in Blender Cycles and graded in After Effects.",
      tools: ["Blender", "After Effects"],
    },
    {
      title: "Festival Social Pack",
      category: "Social Content",
      year: "2025",
      color: "#2eff9a",
      style: "grid",
      preview: "", video: "", images: [],
      brief: "A toolkit of animated templates (9:16 and 1:1) for a music festival's lineup announcements and countdowns.",
      role: "Design system & templates",
      process: "Built a modular grid system so the client could swap artist names and dates inside Essential Graphics templates without breaking the animation.",
      tools: ["After Effects", "Premiere Pro"],
    },
    {
      title: "Signal — UI Micro-interactions",
      category: "UI Motion",
      year: "2024",
      color: "#ff4fa3",
      style: "wave",
      preview: "", video: "", images: [],
      brief: "Motion language for a music app: buttons, loaders, transitions and the 'now playing' visualiser.",
      role: "Motion design & dev handoff",
      process: "Defined easing and duration tokens, prototyped in After Effects, and exported Lottie files so developers could ship the exact animations.",
      tools: ["After Effects", "Figma", "Lottie"],
    },
  ],
};
