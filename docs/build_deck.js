// Builds docs/ScholarDesk_CA3.pptx  —  node build_deck.js
const path = require("path");
const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");
const { applyTheme } = require("/root/.claude/skills/synced/a4a09aec-0032-43e6-b744-c7322f0ac396_db5b118d-796a-41d1-8348-5ad1cebf98b4/pptx/scripts/apply_theme.js");

const LIVE = "scholardesk-wpdp.onrender.com";
const REPO = "github.com/Saafalya/scholardesk-";

const THEME = {
  name: "Scholarship Desk",
  headFontFace: "Arial",
  bodyFontFace: "Calibri",
  colors: {
    dk1: "1B2A41", lt1: "FFFFFF", dk2: "55627A", lt2: "EEF1F5",
    accent1: "1B2A41", accent2: "2E7D4F", accent3: "B3261E", accent4: "A5640C",
    accent5: "C9D2DE", accent6: "7FA3D6", hlink: "2E5E9E", folHlink: "55627A",
  },
};
const HEX = THEME.colors;

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9"; // 10 x 5.625
  pres.author = "Saafalya Sengupta, Swastik Gavhane";
  pres.title = "Scholarship Screening Desk — CA-3 Agentic AI PoC";
  pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
  const C = pres.SchemeColor;

  // ---------------------------------------------------------------- layouts
  pres.defineSlideMaster({
    title: "Dark title",
    background: { color: C.text1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.6, y: 1.35, w: 6.4, h: 1.6, fontSize: 40, bold: true,
          color: C.background1, valign: "top", align: "left", margin: 0 }, text: "" } },
      { placeholder: { options: { name: "body", type: "body", x: 0.6, y: 3.05, w: 6.0, h: 0.9, fontSize: 16,
          color: "C9D2DE", valign: "top", align: "left", margin: 0 }, text: "" } },
    ],
  });
  pres.defineSlideMaster({
    title: "Title only",
    background: { color: C.background1 },
    objects: [
      { placeholder: { options: { name: "title", type: "title", x: 0.5, y: 0.32, w: 9.0, h: 0.7, fontSize: 26, bold: true,
          color: C.text1, valign: "middle", align: "left", margin: 0 }, text: "" } },
      { text: { text: "Scholarship Screening Desk · Saafalya Sengupta & Swastik Gavhane · AIML C1",
          options: { x: 0.5, y: 5.22, w: 6, h: 0.25, fontSize: 9, color: C.text2, margin: 0 } } },
    ],
    slideNumber: { x: 9.1, y: 5.22, w: 0.4, h: 0.25, fontSize: 9, color: C.text2, align: "right" },
  });

  // stamp motif: rotated double-bordered tag, the same element the app uses for verdicts
  function stamp(slide, text, x, y, w, color, rot = -5, size = 18) {
    const h = size / 40 + 0.28;
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.06, rotate: rot,
      fill: { type: "none" }, line: { color, width: 2.25 }, objectName: `stamp-outer-${text}` });
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.05, y: y + 0.05, w: w - 0.1, h: h - 0.1, rectRadius: 0.04,
      rotate: rot, fill: { type: "none" }, line: { color, width: 1 }, objectName: `stamp-inner-${text}` });
    slide.addText(text, { x, y, w, h, rotate: rot, align: "center", valign: "middle", fontFace: "Arial", bold: true,
      fontSize: size, color, charSpacing: 2, margin: 0, isTextBox: true, objectName: `stamp-text-${text}` });
  }

  // ================================================================ 1. title
  pres.addSection({ title: "Opening" });
  let s = pres.addSlide({ masterName: "Dark title", sectionTitle: "Opening" });
  s.addText("Scholarship Screening Desk", { placeholder: "title" });
  s.addText("Six AI agents that screen scholarship applications, check every rule and explain each decision",
    { placeholder: "body" });
  stamp(s, "ELIGIBLE", 7.25, 1.55, 2.1, "7FC79A", -7, 22);
  s.addText([
    { text: "Saafalya Sengupta · PRN 24070126158", options: { bold: true, color: HEX.lt1, breakLine: true } },
    { text: "Swastik Gavhane · PRN 24070126224", options: { bold: true, color: HEX.lt1, breakLine: true } },
    { text: "AIML C1 · CA-3 Agentic AI PoC", options: { color: "C9D2DE" } },
  ], { x: 0.6, y: 4.1, w: 6.5, h: 0.95, fontSize: 13, margin: 0, isTextBox: true, objectName: "byline" });
  s.addText("Domain: Education", { x: 7.25, y: 4.75, w: 2.2, h: 0.3, fontSize: 12, color: "C9D2DE", align: "right",
    margin: 0, isTextBox: true, objectName: "domain" });
  s.addNotes("Hi, we're Saafalya and Swastik. Our project is the Scholarship Screening Desk, an agentic AI proof of concept in the education domain. It uses six agents to screen scholarship applications the way a college office does, but with every rule checked and every decision explained.");

  // ================================================================ 2. problem
  pres.addSection({ title: "Problem" });
  s = pres.addSlide({ masterName: "Title only", sectionTitle: "Problem" });
  s.addText("Screening today is slow, uneven and unexplained", { placeholder: "title" });
  s.addText([
    { text: "How it works today", options: { bold: true, fontSize: 16, breakLine: true } },
    { text: "Students submit a form plus an income certificate, a marksheet and, for reserved categories, a category certificate. Office staff check each application against six rules by hand, then build a shortlist in a spreadsheet.",
      options: { fontSize: 14, color: C.text2 } },
  ], { x: 0.5, y: 1.25, w: 4.1, h: 2.0, valign: "top", margin: 0, paraSpaceAfter: 6, isTextBox: true, objectName: "today" });
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 3.4, w: 4.1, h: 1.5, rectRadius: 0.08,
    fill: { color: C.background2 }, line: { type: "none" }, objectName: "statement-bg" });
  s.addText([
    { text: "Problem statement", options: { bold: true, fontSize: 13, breakLine: true } },
    { text: "Manual screening is slow, inconsistent between reviewers, misses form-versus-marksheet mismatches, and rarely tells a rejected student why.",
      options: { fontSize: 13 } },
  ], { x: 0.7, y: 3.5, w: 3.7, h: 1.3, valign: "top", margin: 0, isTextBox: true, objectName: "statement" });

  const pains = [
    [fa.FaKeyboard, "Typing errors", "Income and CGPA are re-typed into a sheet by hand"],
    [fa.FaBalanceScale, "Uneven rules", "Two reviewers can read the same cutoff differently"],
    [fa.FaSearch, "Mismatches slip through", "Inflated CGPA on the form is rarely cross-checked"],
    [fa.FaQuestionCircle, "No reasons", "Rejected students rarely learn which rule they failed"],
  ];
  for (let i = 0; i < pains.length; i++) {
    const [I, head, sub] = pains[i];
    const y = 1.25 + i * 0.95;
    s.addShape(pres.shapes.OVAL, { x: 5.1, y, w: 0.62, h: 0.62, fill: { color: C.text1 }, line: { type: "none" }, objectName: `pain-dot-${i}` });
    s.addImage({ data: await icon(I, "FFFFFF"), x: 5.26, y: y + 0.16, w: 0.3, h: 0.3, altText: head, objectName: `pain-icon-${i}` });
    s.addText([
      { text: head, options: { bold: true, fontSize: 15, breakLine: true } },
      { text: sub, options: { fontSize: 13, color: C.text2 } },
    ], { x: 5.92, y: y - 0.04, w: 3.6, h: 0.72, valign: "middle", margin: 0, isTextBox: true, objectName: `pain-${i}` });
  }
  s.addNotes("Today a scholarship office reads each form, opens each attachment, and checks six rules by hand: income, CGPA cutoff by category, attendance, documents, whether the form CGPA matches the marksheet, and whether the student already has a full award. That causes typing errors, uneven decisions, missed mismatches, and no written reason for rejections.");

  // ================================================================ 3. solution: six agents
  pres.addSection({ title: "Solution" });
  s = pres.addSlide({ masterName: "Title only", sectionTitle: "Solution" });
  s.addText("Six agents split the job the way an office would", { placeholder: "title" });
  const agents = [
    [fa.FaRoute, "Planner", "Decides which checks apply, such as relaxed cutoffs for reserved categories", "Ollama", false],
    [fa.FaFileAlt, "Extractor", "Pulls income, CGPA, attendance and other fields from free text", "Ollama", false],
    [fa.FaUserCheck, "Critic", "Re-reads the source, sends wrong extractions back, checks the final verdict", "Python", true],
    [fa.FaTools, "Validator", "Executor: runs six rule checks as Python tool calls", "Python", false],
    [fa.FaGavel, "Decision", "Eligible, not eligible or needs documents, plus a merit-cum-means score", "Python", false],
    [fa.FaPenFancy, "Reporter", "Writes a plain-English reason for the reviewer", "Ollama", false],
  ];
  for (let i = 0; i < agents.length; i++) {
    const [I, name, job, engine, critic] = agents[i];
    const col = i % 3, row = Math.floor(i / 3);
    const x = 0.5 + col * 3.05, y = 1.2 + row * 1.95, w = 2.85, h = 1.75;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.08,
      fill: { color: critic ? "FFF6E8" : HEX.lt2 }, line: { color: critic ? HEX.accent4 : HEX.lt2, width: 1 }, objectName: `agent-card-${name}` });
    s.addShape(pres.shapes.OVAL, { x: x + 0.2, y: y + 0.2, w: 0.5, h: 0.5, fill: { color: critic ? C.accent4 : C.text1 }, line: { type: "none" }, objectName: `agent-dot-${name}` });
    s.addImage({ data: await icon(I, "FFFFFF"), x: x + 0.33, y: y + 0.33, w: 0.24, h: 0.24, altText: name, objectName: `agent-icon-${name}` });
    s.addText(name, { x: x + 0.82, y: y + 0.2, w: 1.3, h: 0.5, fontSize: 16, bold: true, valign: "middle", margin: 0, isTextBox: true, objectName: `agent-name-${name}` });
    s.addText(engine, { x: x + 1.95, y: y + 0.3, w: 0.75, h: 0.3, fontSize: 10, color: C.text2, align: "right", valign: "middle", margin: 0, isTextBox: true, objectName: `agent-engine-${name}` });
    s.addText(job, { x: x + 0.2, y: y + 0.82, w: w - 0.4, h: 0.82, fontSize: 13, color: C.text1, valign: "top", margin: 0, isTextBox: true, objectName: `agent-job-${name}` });
  }
  s.addNotes("I split the work across six agents. The Planner decides which checks apply. The Extractor uses a local Ollama model to read the free-text form and marksheet. The Critic, in amber, independently re-reads the source and sends the case back if a field is wrong. The Validator is the executor: it calls six Python rule tools. The Decision agent gives one of three verdicts and a score. The Reporter writes the reason in plain English.");

  // ================================================================ 4. architecture
  pres.addSection({ title: "Architecture" });
  s = pres.addSlide({ masterName: "Title only", sectionTitle: "Architecture" });
  s.addText("Architecture: one orchestrator, one shared state", { placeholder: "title" });
  s.addImage({ path: path.join(__dirname, "architecture.png"), x: 1.38, y: 1.08, w: 7.24, h: 4.07,
    altText: "Architecture diagram: inputs to Streamlit UI, orchestrator running Planner, Extractor, Critic, Validator, Decision, Critic, Reporter, with Ollama model, Python tools and awards registry",
    objectName: "architecture" });
  s.addNotes("Here is the architecture. The Streamlit UI passes a case to a Python orchestrator, which runs the agents in order and keeps one shared state per case. The dashed amber loop is the Critic sending the case back to the Extractor. Planner, Extractor and Reporter call Ollama; the Validator calls plain Python tools, one of which checks a JSON awards registry. If Ollama isn't running, a built-in rule model takes over with the same interface.");

  // ================================================================ 5. decisions
  s = pres.addSlide({ masterName: "Title only", sectionTitle: "Architecture" });
  s.addText("Where the agents make decisions", { placeholder: "title" });
  const flow = ["Planner", "Extractor", "Critic", "Validator", "Decision", "Critic", "Reporter"];
  const fw = 1.1, fg = 0.22, fx = 0.5 + (9 - (flow.length * fw + (flow.length - 1) * fg)) / 2;
  for (let i = 0; i < flow.length; i++) {
    const x = fx + i * (fw + fg);
    const critic = flow[i] === "Critic";
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 1.55, w: fw, h: 0.55, rectRadius: 0.08,
      fill: { color: critic ? "FFF6E8" : HEX.lt1 }, line: { color: critic ? HEX.accent4 : HEX.dk1, width: 1.25 }, objectName: `flow-${i}` });
    s.addText(flow[i], { x, y: 1.55, w: fw, h: 0.55, fontSize: 12, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `flow-t-${i}` });
    if (i) s.addShape(pres.shapes.LINE, { x: x - fg + 0.03, y: 1.825, w: fg - 0.06, h: 0, line: { color: HEX.dk2, width: 1.25, endArrowType: "triangle" }, objectName: `flow-a-${i}` });
  }
  // send-back arc label
  const ex = fx + 1 * (fw + fg), cx2 = fx + 2 * (fw + fg);
  const dash = () => ({ color: HEX.accent4, width: 1.25, dashType: "dash" });
  s.addShape(pres.shapes.LINE, { x: ex + fw / 2, y: 1.3, w: cx2 - ex, h: 0, line: dash(), objectName: "sendback-top" });
  s.addShape(pres.shapes.LINE, { x: cx2 + fw / 2, y: 1.3, w: 0, h: 0.25, line: dash(), objectName: "sendback-up" });
  s.addShape(pres.shapes.LINE, { x: ex + fw / 2, y: 1.3, w: 0, h: 0.23, line: Object.assign(dash(), { endArrowType: "triangle" }), objectName: "sendback-down" });
  s.addText("send back if wrong", { x: cx2 + fw / 2 + 0.1, y: 1.17, w: 1.8, h: 0.26, fontSize: 10, color: C.accent4, margin: 0, isTextBox: true, objectName: "sendback-label" });

  const decisions = [
    ["Planner chooses the checks", "Per case. Reserved categories get a relaxed CGPA cutoff and need a category certificate. A guardrail adds back any mandatory check the model skips."],
    ["Critic accepts, sends back or overrides", "It compares every field with the source text. Wrong fields go back to the Extractor with notes. If retries run out, it overrides them."],
    ["Decision picks one of three outcomes", "Any failed rule means not eligible; anything missing means needs documents. In batch mode, eligible students are ranked and fill the award slots."],
  ];
  for (let i = 0; i < 3; i++) {
    const x = 0.5 + i * 3.05;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: 2.4, w: 2.85, h: 2.6, rectRadius: 0.08, fill: { color: C.background2 }, line: { type: "none" }, objectName: `dec-bg-${i}` });
    s.addText(String(i + 1), { x: x + 0.2, y: 2.52, w: 0.5, h: 0.5, fontSize: 26, bold: true, color: i === 1 ? C.accent4 : C.text1, margin: 0, isTextBox: true, objectName: `dec-n-${i}` });
    s.addText([
      { text: decisions[i][0], options: { bold: true, fontSize: 15, breakLine: true } },
      { text: decisions[i][1], options: { fontSize: 13, color: C.text2 } },
    ], { x: x + 0.2, y: 3.05, w: 2.45, h: 1.85, valign: "top", margin: 0, paraSpaceAfter: 6, isTextBox: true, objectName: `dec-t-${i}` });
  }
  s.addNotes("This is what makes it agentic rather than a fixed script. Three points of judgment. The Planner picks checks per case. The Critic decides whether to accept the extraction, send it back with notes, or override it. The Decision agent picks one of three outcomes, and in batch mode the orchestrator decides who is awarded and who is waitlisted based on how many awards are available.");

  // ================================================================ 6. demo
  pres.addSection({ title: "Demo" });
  s = pres.addSlide({ masterName: "Title only", sectionTitle: "Demo" });
  s.addText("Demo: the Critic catches a slip", { placeholder: "title" });
  s.addImage({ path: path.join(__dirname, "shots/02_case_verdict.png"), x: 0.5, y: 1.15, w: 3.6, h: 3.86,
    altText: "Screenshot of the app screening application MCM-2026-002 with a NOT ELIGIBLE stamp, rule checks and the agent trace",
    objectName: "demo-shot" });
  const demoX = 4.4;
  const steps = [
    ["Pick an application", "MCM-2026-002, Rohan Deshmukh, OBC. The demo switch makes the Extractor slip once."],
    ["Critic sends it back", "Trace steps 3–6: the Critic spots a wrong field, the Extractor re-reads, the Critic accepts."],
    ["Validator runs six tools", "Five pass. check_consistency fails: form says 8.40, marksheet says 7.70."],
    ["Stamp and reason", "Not eligible, with the exact rule named for the reviewer."],
  ];
  for (let i = 0; i < steps.length; i++) {
    const y = 1.15 + i * 0.98;
    s.addShape(pres.shapes.OVAL, { x: demoX, y, w: 0.42, h: 0.42, fill: { color: C.text1 }, line: { type: "none" }, objectName: `demo-dot-${i}` });
    s.addText(String(i + 1), { x: demoX, y, w: 0.42, h: 0.42, fontSize: 13, bold: true, color: C.background1, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: `demo-n-${i}` });
    s.addText([
      { text: steps[i][0], options: { bold: true, fontSize: 15, breakLine: true } },
      { text: steps[i][1], options: { fontSize: 13, color: C.text2 } },
    ], { x: demoX + 0.6, y: y - 0.06, w: 4.5, h: 0.9, valign: "top", margin: 0, isTextBox: true, objectName: `demo-t-${i}` });
  }
  s.addText(`Live: ${LIVE}`, { x: demoX + 0.6, y: 4.95, w: 4.5, h: 0.25, fontSize: 11, color: C.accent2, bold: true, margin: 0, isTextBox: true, objectName: "demo-link",
    hyperlink: { url: "https://" + LIVE } });
  s.addNotes("Switch to the app now. Pick MCM-2026-002, turn on 'Make the Extractor slip once', and press Screen. Point at the trace: the Critic finds a mismatch, the orchestrator sends it back, the Extractor re-reads and the Critic accepts. Then the Validator runs six tools. Five pass, but the form says CGPA 8.40 while the marksheet says 7.70, so it's not eligible. Then switch to the batch tab, set four awards, and screen all twelve.");

  // ================================================================ 7. results
  pres.addSection({ title: "Results" });
  s = pres.addSlide({ masterName: "Title only", sectionTitle: "Results" });
  s.addText("Validated against hand-checked answers", { placeholder: "title" });
  const stats = [["12/12", "verdicts match the hand-checked labels", C.accent2],
                 ["12/12", "injected extraction slips caught by the Critic", C.accent4],
                 ["0", "verdicts contradicted by the rule results", C.text1]];
  for (let i = 0; i < stats.length; i++) {
    const y = 1.2 + i * 1.25;
    s.addText(stats[i][0], { x: 0.5, y, w: 1.9, h: 0.8, fontSize: 44, bold: true, color: stats[i][2], valign: "middle", margin: 0, isTextBox: true, objectName: `stat-n-${i}` });
    s.addText(stats[i][1], { x: 2.45, y, w: 2.3, h: 0.8, fontSize: 14, color: C.text1, valign: "middle", margin: 0, isTextBox: true, objectName: `stat-t-${i}` });
  }
  s.addChart(pres.charts.BAR, [{ name: "Applications", labels: ["Awarded", "Waitlisted", "Needs documents", "Not eligible"], values: [4, 1, 2, 5] }], {
    x: 5.1, y: 1.1, w: 4.4, h: 3.0, barDir: "bar",
    chartColors: [HEX.accent2, HEX.dk1, HEX.accent4, HEX.accent3],
    showTitle: true, title: "Batch of 12 applications, 4 awards available", titleFontSize: 12, titleColor: HEX.dk1, titleFontFace: "+mn-lt",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt",
    catAxisLabelColor: HEX.dk1, catAxisLabelFontSize: 12, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin",
    valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 45,
    valAxisMaxVal: 6, valAxisMinVal: 0,
    altText: "Bar chart: 4 awarded, 1 waitlisted, 2 need documents, 5 not eligible", objectName: "batch-chart",
  });
  s.addText("Top rank went to an ST student with CGPA 7.80 and income ₹3.6 lakh, ahead of a General student with CGPA 9.12 and ₹5.4 lakh. The score weighs need alongside merit, as the scheme intends.",
    { x: 5.1, y: 4.2, w: 4.4, h: 0.85, fontSize: 12, color: C.text2, valign: "top", margin: 0, isTextBox: true, objectName: "rank-note" });
  s.addNotes("Validation. The twelve synthetic applications each test one rule. All twelve verdicts match my hand-checked labels. With mistakes injected, the Critic caught all twelve and the final verdicts didn't change. And the Critic's second check found zero verdicts that contradict the rule results. I also simulated a wrong Ollama answer in the tests and the send-back loop fixed it. In the batch run, four students are awarded and one is waitlisted.");

  // ================================================================ 8. limitations + future
  pres.addSection({ title: "Close" });
  s = pres.addSlide({ masterName: "Title only", sectionTitle: "Close" });
  s.addText("Limitations and what comes next", { placeholder: "title" });
  const cols = [
    ["Limitations", fa.FaExclamationTriangle, HEX.accent3, [
      "Synthetic, clean text; real forms are scanned PDFs",
      "Small local model can misread numbers or break JSON",
      "Render free tier has too little RAM for Ollama, so the hosted demo uses the rule model",
      "Checks that documents exist, not that they are genuine",
    ]],
    ["Future scope", fa.FaArrowRight, HEX.accent2, [
      "OCR so the Extractor reads scanned certificates",
      "Rules editable in the app for several schemes",
      "LangGraph orchestration and MCP-exposed rule tools",
      "Draft each student's result email automatically",
    ]],
  ];
  for (let c = 0; c < 2; c++) {
    const [head, I, col, items] = cols[c];
    const x = 0.5 + c * 4.65;
    s.addShape(pres.shapes.OVAL, { x, y: 1.2, w: 0.5, h: 0.5, fill: { color: col }, line: { type: "none" }, objectName: `col-dot-${c}` });
    s.addImage({ data: await icon(I, "FFFFFF"), x: x + 0.13, y: 1.33, w: 0.24, h: 0.24, altText: head, objectName: `col-icon-${c}` });
    s.addText(head, { x: x + 0.65, y: 1.2, w: 3.5, h: 0.5, fontSize: 18, bold: true, valign: "middle", margin: 0, isTextBox: true, objectName: `col-h-${c}` });
    s.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1 } })),
      { x, y: 1.9, w: 4.2, h: 2.9, fontSize: 14, color: C.text1, valign: "top", margin: 0, paraSpaceAfter: 10, isTextBox: true, objectName: `col-list-${c}` });
  }
  s.addNotes("Limitations: the data is synthetic and clean, the local model is small, and Render's free tier can't run Ollama, so the hosted link uses the rule model. Next steps would be OCR for scanned documents, rules the office can edit, moving to LangGraph and MCP, and drafting result emails to students.");

  // ================================================================ 9. close
  s = pres.addSlide({ masterName: "Dark title", sectionTitle: "Close" });
  s.addText("Thank you", { placeholder: "title" });
  s.addText("Questions welcome", { placeholder: "body" });
  stamp(s, "REVIEWED", 7.15, 1.55, 2.2, "7FA3D6", -6, 20);
  s.addText([
    { text: "Live app  ", options: { color: "C9D2DE" } },
    { text: LIVE, options: { color: HEX.lt1, bold: true, hyperlink: { url: "https://" + LIVE }, breakLine: true } },
    { text: "Code  ", options: { color: "C9D2DE" } },
    { text: REPO, options: { color: HEX.lt1, bold: true, hyperlink: { url: "https://" + REPO } } },
  ], { x: 0.6, y: 4.2, w: 8.5, h: 0.75, fontSize: 14, margin: 0, isTextBox: true, objectName: "links" });
  s.addNotes("Thank you. The app is live on Render and the code is on GitHub. Happy to take questions.");

  const out = path.join(__dirname, "ScholarDesk_CA3.pptx");
  await pres.writeFile({ fileName: out });
  await applyTheme(out, THEME);
  console.log("wrote", out);
})();
