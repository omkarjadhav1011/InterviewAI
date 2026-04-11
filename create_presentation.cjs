const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "AI-Powered Interview Preparation System";
pres.author = "Omkar Jadhav";

// ─── Palette ──────────────────────────────────────────────────────────────────
const C = {
  navy:      "0D2137",
  blue:      "1A56DB",
  lightBlue: "EFF6FF",
  white:     "FFFFFF",
  darkText:  "1E293B",
  mutedText: "64748B",
  border:    "CBD5E1",
  light:     "F1F5F9",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────
function mkShadow() {
  return { type: "outer", blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.08 };
}

function addHeader(slide, title, num) {
  slide.background = { color: C.lightBlue };
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 10, h: 0.72,
    fill: { color: C.navy }, line: { color: C.navy },
  });
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.08, h: 0.72,
    fill: { color: C.blue }, line: { color: C.blue },
  });
  slide.addText(title, {
    x: 0.35, y: 0, w: 9.2, h: 0.72,
    fontSize: 22, fontFace: "Calibri", bold: true,
    color: C.white, valign: "middle", margin: 0,
  });
  slide.addText(String(num), {
    x: 9.2, y: 5.2, w: 0.6, h: 0.3,
    fontSize: 9, fontFace: "Calibri", color: C.mutedText, align: "right",
  });
}

function bullets(items) {
  return items.map((text, i) => ({
    text,
    options: { bullet: true, breakLine: i < items.length - 1 },
  }));
}

// ─── Slide 1 · Title ──────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  // Decorative circles (top-right)
  s.addShape(pres.shapes.OVAL, { x: 7.4, y: -0.9, w: 3.6, h: 3.6, fill: { color: "1A3050" }, line: { color: "1A3050" } });
  s.addShape(pres.shapes.OVAL, { x: 8.0, y: -0.4, w: 2.5, h: 2.5, fill: { color: "152840" }, line: { color: "152840" } });

  // Bottom accent bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 4.9, w: 10, h: 0.725, fill: { color: C.blue }, line: { color: C.blue } });

  // Tag
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.05, w: 1.7, h: 0.3, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("MEGA PROJECT", {
    x: 0.5, y: 1.05, w: 1.7, h: 0.3,
    fontSize: 8, fontFace: "Calibri", bold: true, color: C.white,
    align: "center", valign: "middle", margin: 0,
  });

  // Title
  s.addText("AI-Powered Interview\nPreparation System", {
    x: 0.5, y: 1.5, w: 8.5, h: 1.9,
    fontSize: 38, fontFace: "Calibri", bold: true, color: C.white, valign: "top",
  });

  // Divider
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 3.45, w: 1.1, h: 0.05, fill: { color: C.blue }, line: { color: C.blue } });

  // Meta info
  s.addText([
    { text: "Omkar Jadhav", options: { bold: true, breakLine: true } },
    { text: "[College Name]  ·  [Department]", options: { breakLine: true } },
    { text: "Guide: [Guide Name]  ·  Academic Year: [Year]", options: {} },
  ], {
    x: 0.5, y: 3.6, w: 7, h: 1.1,
    fontSize: 13, fontFace: "Calibri", color: "A8C4E0",
  });
}

// ─── Slide 2 · Introduction ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Introduction", 2);

  s.addText(bullets([
    "An AI-driven web application that automates mock interview practice",
    "Parses resumes to extract skills; generates personalized questions via Google Gemini 2.0",
    "Supports voice-based answering with real-time speech-to-text transcription (AssemblyAI)",
    "Evaluates answers for technical accuracy, confidence, and communication quality",
    "Provides detailed per-question feedback and full-interview analysis after each session",
  ]), {
    x: 0.5, y: 0.92, w: 6.2, h: 4.4,
    fontSize: 14, fontFace: "Calibri", color: C.darkText, paraSpaceAfter: 9,
  });

  // Info card (right)
  s.addShape(pres.shapes.RECTANGLE, { x: 7.1, y: 0.95, w: 2.6, h: 4.0, fill: { color: C.navy }, line: { color: C.navy } });
  const info = [
    ["Platform", "Web App"],
    ["AI Engine", "Gemini 2.0"],
    ["Speech-to-Text", "AssemblyAI"],
    ["Backend", "Flask / Python"],
    ["Database", "MongoDB"],
  ];
  info.forEach(([label, value], i) => {
    const y = 1.1 + i * 0.75;
    s.addText(label, { x: 7.25, y, w: 2.3, h: 0.22, fontSize: 9, bold: true, color: "7EB3D8", fontFace: "Calibri", margin: 0 });
    s.addText(value, { x: 7.25, y: y + 0.23, w: 2.3, h: 0.3, fontSize: 13, color: C.white, fontFace: "Calibri", margin: 0 });
  });
}

// ─── Slide 3 · Problem Statement ─────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Problem Statement", 3);

  const problems = [
    "Students lack access to realistic, personalized mock interview practice before placements",
    "Existing tools offer generic questions unrelated to the candidate's actual skillset",
    "No immediate, detailed feedback on technical accuracy or communication skills",
    "Manual interview scheduling is time-consuming for both students and mentors",
    "Voice-based practice is rarely available in free or academic-grade tools",
  ];

  // Row 1: 3 cards; Row 2: 2 cards centered
  problems.forEach((text, i) => {
    let x, y;
    if (i < 3) {
      x = 0.35 + i * 3.1;
      y = 0.92;
    } else {
      x = 0.35 + (i - 3) * 3.1 + 1.55;
      y = 2.78;
    }
    const w = 2.8, h = 1.6;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: C.white }, line: { color: C.border, pt: 1 }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.06, h, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(`0${i + 1}`, { x: x + 0.12, y: y + 0.1, w: 0.5, h: 0.36, fontSize: 18, bold: true, color: C.blue, fontFace: "Calibri", margin: 0 });
    s.addText(text, { x: x + 0.12, y: y + 0.5, w: w - 0.2, h: 1.0, fontSize: 11, color: C.darkText, fontFace: "Calibri", wrap: true, margin: 0 });
  });
}

// ─── Slide 4 · Objectives ─────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Objectives", 4);

  // Aim banner
  s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y: 0.9, w: 9.3, h: 0.62, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("Main Aim: Build an intelligent, automated interview practice platform that evaluates candidates based on their resume skills", {
    x: 0.5, y: 0.9, w: 9.1, h: 0.62,
    fontSize: 12.5, fontFace: "Calibri", bold: true, color: C.white, valign: "middle", margin: 0,
  });

  s.addText(bullets([
    "Automate resume parsing to extract technical and domain skills accurately",
    "Generate role-relevant interview questions using Generative AI (Gemini 2.0)",
    "Enable voice-based answering with real-time speech recognition",
    "Evaluate answers across confidence, technical depth, and communication",
    "Provide actionable feedback with an overall performance score (1–10)",
    "Store interview history to enable continuous self-improvement",
  ]), {
    x: 0.5, y: 1.65, w: 9.0, h: 3.65,
    fontSize: 14, fontFace: "Calibri", color: C.darkText, paraSpaceAfter: 7,
  });
}

// ─── Slide 5 · Scope ──────────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Scope of the Project", 5);

  const addColumn = (x, heading, color, items) => {
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.88, w: 4.55, h: 4.5, fill: { color: C.white }, line: { color: C.border, pt: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.88, w: 4.55, h: 0.42, fill: { color: color }, line: { color: color } });
    s.addText(heading, { x, y: 0.88, w: 4.55, h: 0.42, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle", fontFace: "Calibri", margin: 0 });
    s.addText(bullets(items), { x: x + 0.15, y: 1.42, w: 4.22, h: 3.85, fontSize: 12.5, fontFace: "Calibri", color: C.darkText, paraSpaceAfter: 6 });
  };

  addColumn(0.35, "COVERS", C.navy, [
    "PDF resume upload and NLP skill extraction",
    "AI-generated, skill-based interview questions",
    "Real-time voice transcription (AssemblyAI)",
    "Per-question and full-interview AI evaluation",
    "Dashboard with historical interview results",
    "Web-based access — no installation required",
  ]);

  addColumn(5.1, "LIMITATIONS", C.blue, [
    "Supports PDF resumes only for direct upload",
    "Question generation depends on Gemini API availability",
    "Voice transcription requires internet connectivity",
    "AI evaluation may not fully replicate human judgment",
    "Not yet optimized for mobile browsers",
  ]);
}

// ─── Slide 6 · Literature Review ─────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Literature Review / Existing System", 6);

  const systems = [
    { name: "Pramp", desc: "Peer-to-peer mock interviews. No AI evaluation or resume-based question personalization." },
    { name: "Interview Cake", desc: "Text-based coding challenges only. No voice support, no real-time feedback." },
    { name: "LeetCode Mock", desc: "Focuses on DSA problems only. No communication or soft-skills assessment." },
    { name: "HireVue", desc: "Enterprise tool. Expensive, complex setup — no student or free-tier access." },
  ];

  systems.forEach((sys, i) => {
    const y = 0.92 + i * 0.98;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y, w: 9.3, h: 0.82, fill: { color: C.white }, line: { color: C.border, pt: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y, w: 0.06, h: 0.82, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(sys.name, { x: 0.55, y: y + 0.08, w: 1.9, h: 0.3, fontSize: 13, bold: true, color: C.navy, fontFace: "Calibri", margin: 0 });
    s.addText(sys.desc, { x: 0.55, y: y + 0.42, w: 9.0, h: 0.3, fontSize: 11.5, color: C.darkText, fontFace: "Calibri", margin: 0 });
  });

  // Gap banner
  s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y: 5.0, w: 9.3, h: 0.38, fill: { color: "FFF3CD" }, line: { color: "FFC107", pt: 1 } });
  s.addText("Common Gap: No existing tool combines resume parsing + AI evaluation + voice practice in a single free platform.", {
    x: 0.5, y: 5.0, w: 9.1, h: 0.38,
    fontSize: 11, bold: true, color: "856404", valign: "middle", fontFace: "Calibri", margin: 0,
  });
}

// ─── Slide 7 · Proposed System ───────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.07, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("Proposed System", { x: 0.5, y: 0.2, w: 9, h: 0.7, fontSize: 28, bold: true, color: C.white, fontFace: "Calibri" });

  const features = [
    { title: "Resume Intelligence",   desc: "PDF parsing + spaCy NLP extracts tech skills matched against a curated SKILLS_DB of 100+ technologies" },
    { title: "AI Question Engine",    desc: "Google Gemini 2.0 generates context-aware, skill-specific questions with a keyword-based fallback" },
    { title: "Voice + Text Answers",  desc: "Real-time STT via AssemblyAI WebSocket; combines voice transcript with typed supplements intelligently" },
    { title: "Smart Evaluation",      desc: "AI scores each answer for confidence, technical depth, and communication; delivers full post-interview analysis" },
  ];

  features.forEach((f, i) => {
    const x = 0.35 + (i % 2) * 4.85;
    const y = 1.15 + Math.floor(i / 2) * 1.88;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.55, h: 1.68, fill: { color: "1A3050" }, line: { color: "2A4570" } });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.07, h: 1.68, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(f.title, { x: x + 0.16, y: y + 0.12, w: 4.2, h: 0.32, fontSize: 13, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(f.desc, { x: x + 0.16, y: y + 0.5, w: 4.2, h: 1.05, fontSize: 11, color: "A8C4E0", fontFace: "Calibri", wrap: true, margin: 0 });
  });

  s.addText("7", { x: 9.2, y: 5.2, w: 0.6, h: 0.3, fontSize: 9, color: "4A6080", align: "right", fontFace: "Calibri" });
}

// ─── Slide 8 · Methodology ───────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Methodology", 8);

  const steps = [
    { n: "1", title: "Resume Upload",    desc: "User uploads PDF via web interface" },
    { n: "2", title: "Skill Extraction", desc: "NLP parser extracts skills; matched vs. SKILLS_DB" },
    { n: "3", title: "Question Gen.",    desc: "Gemini API creates 5–7 personalized questions" },
    { n: "4", title: "User Answers",     desc: "Voice (STT) or typed input; combined automatically" },
    { n: "5", title: "AI Evaluation",    desc: "Gemini scores each answer; full analysis at end" },
    { n: "6", title: "Results",          desc: "Scores, feedback, and improvement areas displayed" },
  ];

  steps.forEach((step, i) => {
    const x = 0.35 + (i % 3) * 3.15;
    const y = i < 3 ? 0.92 : 3.1;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 2.9, h: 1.92, fill: { color: C.white }, line: { color: C.border, pt: 1 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.12, y: y + 0.16, w: 0.44, h: 0.44, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(step.n, { x: x + 0.12, y: y + 0.16, w: 0.44, h: 0.44, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle", fontFace: "Calibri", margin: 0 });
    s.addText(step.title, { x: x + 0.65, y: y + 0.18, w: 2.1, h: 0.33, fontSize: 12, bold: true, color: C.navy, fontFace: "Calibri", margin: 0 });
    s.addText(step.desc, { x: x + 0.12, y: y + 0.72, w: 2.65, h: 1.05, fontSize: 11, color: C.darkText, fontFace: "Calibri", wrap: true, margin: 0 });
    // Connector arrow (within same row, not last in row)
    if (i % 3 < 2) {
      s.addShape(pres.shapes.RECTANGLE, { x: x + 2.95, y: y + 0.88, w: 0.2, h: 0.06, fill: { color: C.blue }, line: { color: C.blue } });
    }
  });

  // Tech bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.15, w: 10, h: 0.3, fill: { color: C.navy }, line: { color: C.navy } });
  s.addText("Technologies: Python · Flask · Google Gemini 2.0 · AssemblyAI · MongoDB · HTML / CSS / JavaScript", {
    x: 0, y: 5.15, w: 10, h: 0.3,
    fontSize: 10, fontFace: "Calibri", color: C.white, align: "center", valign: "middle", margin: 0,
  });
}

// ─── Slide 9 · System Architecture ───────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "System Architecture / Design", 9);

  const layers = [
    { label: "Frontend Layer",   detail: "HTML Templates  ·  CSS3  ·  JavaScript  ·  interview.js  ·  whisper_transcription.js", bg: "EFF6FF", border: C.blue },
    { label: "Backend Layer",    detail: "Flask Routes  ·  Auth BP  ·  Resume BP  ·  Interview BP  ·  Transcription BP", bg: "F0FDF4", border: "10B981" },
    { label: "AI Services Layer",detail: "Gemini Service  ·  VAPI Service  ·  AssemblyAI Transcription Service", bg: "FFF7ED", border: "F97316" },
    { label: "Data Layer",       detail: "MongoDB Atlas  ·  users collection  ·  interview_runs collection", bg: "FDF4FF", border: "A855F7" },
  ];

  layers.forEach((l, i) => {
    const y = 0.9 + i * 1.05;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y, w: 9.3, h: 0.88, fill: { color: l.bg }, line: { color: l.border, pt: 1.5 } });
    s.addText(l.label, { x: 0.55, y: y + 0.1, w: 2.8, h: 0.28, fontSize: 12, bold: true, color: C.navy, fontFace: "Calibri", margin: 0 });
    s.addText(l.detail, { x: 0.55, y: y + 0.44, w: 9.0, h: 0.32, fontSize: 11.5, color: C.darkText, fontFace: "Calibri", margin: 0 });
    if (i < layers.length - 1) {
      s.addShape(pres.shapes.RECTANGLE, { x: 4.87, y: y + 0.9, w: 0.05, h: 0.12, fill: { color: C.mutedText }, line: { color: C.mutedText } });
    }
  });

  s.addText("Request Flow:  User → Flask Routes → Services → AI / DB → JSON Response → Browser", {
    x: 0.35, y: 5.1, w: 9.3, h: 0.28,
    fontSize: 10.5, fontFace: "Calibri", color: C.mutedText, align: "center",
  });
}

// ─── Slide 10 · Implementation ────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Implementation", 10);

  const cards = [
    {
      heading: "Software Stack",
      items: ["Python 3.x + Flask", "MongoDB Atlas", "Google Gemini 2.0 API", "AssemblyAI WebSocket", "VAPI (TTS / STT fallback)", "HTML5 / CSS3 / JavaScript"],
    },
    {
      heading: "Key Features Built",
      items: ["Resume upload + NLP skill parser", "AI question generator (Gemini)", "Real-time voice transcription", "Per-question AI evaluator", "Full interview batch analysis", "Result dashboard with scores"],
    },
    {
      heading: "Architecture Choices",
      items: ["MVC-lite (Flask Blueprints)", "Session-first state management", "Graceful AI API degradation", "Secure auth (Flask-Login + bcrypt)", "Standardized JSON API responses", "Global error handlers (400/404/500)"],
    },
  ];

  cards.forEach((c, i) => {
    const x = 0.35 + i * 3.15;
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 2.9, h: 4.48, fill: { color: C.white }, line: { color: C.border, pt: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 0.9, w: 2.9, h: 0.44, fill: { color: C.navy }, line: { color: C.navy } });
    s.addText(c.heading, { x: x + 0.08, y: 0.9, w: 2.75, h: 0.44, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle", fontFace: "Calibri", margin: 0 });
    s.addText(bullets(c.items), { x: x + 0.12, y: 1.45, w: 2.66, h: 3.82, fontSize: 12, fontFace: "Calibri", color: C.darkText, paraSpaceAfter: 7 });
  });
}

// ─── Slide 11 · Results / Output ─────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Results / Output", 11);

  const results = [
    { title: "Resume Parsing",      desc: "Skills extracted: Python, Flask, MongoDB, REST APIs, NLP, JavaScript, etc." },
    { title: "Question Generation", desc: "5 targeted, skill-specific questions generated per interview session via Gemini AI" },
    { title: "Voice Transcription", desc: "Real-time transcript appears as user speaks; merged with typed input automatically" },
    { title: "Per-Question Score",  desc: "Confidence: 80%  ·  Technical: 75%  ·  Communication: 85%  ·  Overall: 8.0 / 10" },
    { title: "Full Interview Report", desc: "Aggregated scores, identified strengths, areas to improve, and actionable feedback" },
  ];

  results.forEach((r, i) => {
    const y = 0.92 + i * 0.87;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y, w: 9.3, h: 0.75, fill: { color: C.white }, line: { color: C.border, pt: 1 } });
    s.addShape(pres.shapes.OVAL, { x: 0.42, y: y + 0.15, w: 0.42, h: 0.42, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(String(i + 1), { x: 0.42, y: y + 0.15, w: 0.42, h: 0.42, fontSize: 12, bold: true, color: C.white, align: "center", valign: "middle", fontFace: "Calibri", margin: 0 });
    s.addText(r.title + ":", { x: 0.96, y: y + 0.07, w: 2.1, h: 0.28, fontSize: 12, bold: true, color: C.navy, fontFace: "Calibri", margin: 0 });
    s.addText(r.desc, { x: 0.96, y: y + 0.38, w: 8.55, h: 0.28, fontSize: 11.5, color: C.darkText, fontFace: "Calibri", margin: 0 });
  });
}

// ─── Slide 12 · Advantages ────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Advantages", 12);

  s.addText(bullets([
    "Fully personalized — questions generated from each user's own resume skills",
    "Available 24 / 7 — practice anytime without scheduling a human interviewer",
    "Multi-modal input — voice and typed answers combined intelligently",
    "Instant AI feedback — detailed scoring immediately after every answer",
    "Free to use — open-source stack with free API tiers; accessible to all students",
    "Progress tracking — interview history stored for continuous improvement",
    "Resilient system — graceful fallback when AI APIs are unavailable",
  ]), {
    x: 0.5, y: 0.92, w: 9.0, h: 4.4,
    fontSize: 14, fontFace: "Calibri", color: C.darkText, paraSpaceAfter: 9,
  });
}

// ─── Slide 13 · Applications ─────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Applications", 13);

  const apps = [
    { title: "Campus Placement Prep",     desc: "Final-year students preparing for company-specific technical and HR interview rounds" },
    { title: "Coding Bootcamp Graduates", desc: "Bootcamp graduates practicing before their first job applications" },
    { title: "Remote Hiring Screening",   desc: "Automated first-round screening before a human interviewer engages the candidate" },
    { title: "HR Training Tool",          desc: "Training HR staff to understand AI-based evaluation criteria and scoring models" },
    { title: "Career Transition Prep",    desc: "Professionals upskilling and rehearsing for interviews in a new domain" },
    { title: "Academic Research",         desc: "Dataset generation for NLP research on interview scoring and candidate assessment" },
  ];

  apps.forEach((a, i) => {
    const x = 0.35 + (i % 2) * 4.85;
    const y = 0.9 + Math.floor(i / 2) * 1.46;
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 4.55, h: 1.28, fill: { color: C.white }, line: { color: C.border, pt: 1 }, shadow: mkShadow() });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.07, h: 1.28, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(a.title, { x: x + 0.16, y: y + 0.1, w: 4.25, h: 0.3, fontSize: 12, bold: true, color: C.navy, fontFace: "Calibri", margin: 0 });
    s.addText(a.desc, { x: x + 0.16, y: y + 0.46, w: 4.25, h: 0.72, fontSize: 11, color: C.darkText, fontFace: "Calibri", wrap: true, margin: 0 });
  });
}

// ─── Slide 14 · Future Scope ──────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Future Scope", 14);

  const phases = [
    { phase: "Phase 1", items: ["Support DOCX and LinkedIn profile import for skill extraction", "Add interview difficulty levels: Beginner / Intermediate / Advanced"] },
    { phase: "Phase 2", items: ["Integrate video recording and emotion / facial expression analysis", "Leaderboard and competitive mock interview mode between peers"] },
    { phase: "Phase 3", items: ["Company-specific templates (Google, Amazon, TCS, Infosys formats)", "Mobile application with offline mode for basic practice sessions"] },
  ];

  phases.forEach((p, i) => {
    const y = 0.92 + i * 1.45;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y, w: 9.3, h: 1.28, fill: { color: C.white }, line: { color: C.border, pt: 1 } });
    s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y, w: 1.3, h: 1.28, fill: { color: C.navy }, line: { color: C.navy } });
    s.addText(p.phase, { x: 0.35, y, w: 1.3, h: 1.28, fontSize: 13, bold: true, color: C.white, align: "center", valign: "middle", fontFace: "Calibri", margin: 0 });
    s.addText(bullets(p.items), { x: 1.75, y: y + 0.2, w: 7.75, h: 0.9, fontSize: 12.5, fontFace: "Calibri", color: C.darkText, paraSpaceAfter: 4 });
  });

  s.addText("The platform has strong potential to grow into a full AI hiring assistant for enterprises and institutions.", {
    x: 0.35, y: 5.1, w: 9.3, h: 0.28,
    fontSize: 11, fontFace: "Calibri", color: C.mutedText, italic: true, align: "center",
  });
}

// ─── Slide 15 · Conclusion ────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.07, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("Conclusion", { x: 0.5, y: 0.2, w: 9, h: 0.72, fontSize: 28, bold: true, color: C.white, fontFace: "Calibri" });

  s.addText(bullets([
    "Successfully built a full-stack AI-powered interview preparation web application",
    "Integrates Google Gemini 2.0, AssemblyAI, and MongoDB for an end-to-end intelligent pipeline",
    "Personalized questions, real-time voice support, and instant feedback differentiate the system",
    "Addresses a real gap in accessible, high-quality interview practice tools for students",
    "Demonstrates production-ready use of modern AI APIs within a Flask MVC architecture",
  ]), {
    x: 0.5, y: 1.1, w: 9.0, h: 3.8,
    fontSize: 14, fontFace: "Calibri", color: "A8C4E0", paraSpaceAfter: 11,
  });

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.22, w: 10, h: 0.405, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("AI-Powered Interview Preparation System  ·  Omkar Jadhav  ·  [Academic Year]", {
    x: 0, y: 5.22, w: 10, h: 0.405,
    fontSize: 10, fontFace: "Calibri", color: C.white, align: "center", valign: "middle", margin: 0,
  });

  s.addText("15", { x: 9.2, y: 4.88, w: 0.6, h: 0.3, fontSize: 9, color: "4A6080", align: "right", fontFace: "Calibri" });
}

// ─── Slide 16 · References ────────────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "References", 16);

  s.addText([
    { text: "Google. (2024). Gemini API Documentation. Google AI for Developers. https://ai.google.dev", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "AssemblyAI. (2024). Real-Time Speech-to-Text Streaming API. https://www.assemblyai.com/docs", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "MongoDB Inc. (2024). MongoDB Atlas Documentation. https://www.mongodb.com/docs/atlas", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Pallets Projects. (2024). Flask Web Framework Documentation. https://flask.palletsprojects.com", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Honnibal, M. & Montani, I. (2017). spaCy: Industrial-strength Natural Language Processing. Explosion AI.", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "VAPI. (2024). Voice AI Platform API Documentation. https://docs.vapi.ai", options: { bullet: { type: "number" }, breakLine: true } },
    { text: "Vaswani, A. et al. (2017). Attention Is All You Need. Advances in Neural Information Processing Systems.", options: { bullet: { type: "number" } } },
  ], {
    x: 0.5, y: 0.92, w: 9.0, h: 4.4,
    fontSize: 12.5, fontFace: "Calibri", color: C.darkText, paraSpaceAfter: 8,
  });
}

// ─── Slide 17 · Acknowledgement ───────────────────────────────────────────────
{
  const s = pres.addSlide();
  addHeader(s, "Acknowledgement", 17);

  s.addText("We express our sincere gratitude to all those who supported and guided this project:", {
    x: 0.5, y: 0.88, w: 9.0, h: 0.42,
    fontSize: 13, fontFace: "Calibri", color: C.darkText, italic: true,
  });

  const thanks = [
    { to: "[Guide Name]",   role: "Project Guide",      note: "For constant guidance, technical direction, and valuable feedback throughout the project" },
    { to: "[College Name]", role: "Institution",        note: "For providing academic infrastructure, lab facilities, and a learning environment" },
    { to: "[HOD Name]",     role: "Head of Department", note: "For motivating innovative projects and research initiatives among students" },
    { to: "Family & Friends", role: "Personal Support", note: "For continuous encouragement and moral support during project development" },
  ];

  thanks.forEach((t, i) => {
    const y = 1.42 + i * 0.92;
    s.addShape(pres.shapes.RECTANGLE, { x: 0.35, y, w: 9.3, h: 0.78, fill: { color: i % 2 === 0 ? C.white : C.lightBlue }, line: { color: C.border, pt: 1 } });
    s.addText(t.to, { x: 0.5, y: y + 0.08, w: 2.3, h: 0.28, fontSize: 12, bold: true, color: C.navy, fontFace: "Calibri", margin: 0 });
    s.addText(t.role, { x: 0.5, y: y + 0.4, w: 2.3, h: 0.24, fontSize: 10, color: C.blue, fontFace: "Calibri", margin: 0 });
    s.addText(t.note, { x: 2.95, y: y + 0.2, w: 6.55, h: 0.38, fontSize: 11.5, color: C.darkText, fontFace: "Calibri", margin: 0 });
  });
}

// ─── Slide 18 · Q&A / Thank You ──────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  // Decorative circles
  s.addShape(pres.shapes.OVAL, { x: 2.8, y: 0.3, w: 4.4, h: 4.4, fill: { color: "122840" }, line: { color: "1A3050" } });
  s.addShape(pres.shapes.OVAL, { x: 3.4, y: 0.9, w: 3.2, h: 3.2, fill: { color: "162E45" }, line: { color: "1E3A5F" } });

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.blue }, line: { color: C.blue } });

  s.addText("Thank You", {
    x: 0, y: 1.45, w: 10, h: 1.3,
    fontSize: 54, fontFace: "Calibri", bold: true, color: C.white, align: "center",
  });

  s.addText("Questions & Answers", {
    x: 0, y: 2.9, w: 10, h: 0.55,
    fontSize: 20, fontFace: "Calibri", color: "7EB3D8", align: "center",
  });

  s.addText("AI-Powered Interview Preparation System  ·  Omkar Jadhav", {
    x: 0, y: 4.75, w: 10, h: 0.38,
    fontSize: 11, fontFace: "Calibri", color: "4A6080", align: "center",
  });

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.325, w: 10, h: 0.3, fill: { color: C.blue }, line: { color: C.blue } });
}

// ─── Write ────────────────────────────────────────────────────────────────────
pres.writeFile({ fileName: "AI_Interview_Prep_System_Presentation.pptx" })
  .then(() => console.log("✓ Presentation saved: AI_Interview_Prep_System_Presentation.pptx"))
  .catch(err => { console.error("✗ Failed:", err); process.exit(1); });
