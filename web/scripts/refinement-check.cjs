// Focused gstack pass. Baseline mode captures before edits; verify mode checks UI.
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const assert = require("node:assert/strict");
const browser =
  process.env.GSTACK_BROWSER ||
  path.join(
    os.homedir(),
    ".codex/skills/gstack/browse/dist",
    process.platform === "win32" ? "browse.exe" : "browse",
  );
const base = process.env.UI_BASE_URL || "http://127.0.0.1:5174";
const dir = path.resolve(__dirname, "../../docs/ui-review/refinement");
fs.mkdirSync(dir, { recursive: true });
const mode = process.argv[2] || "verify";
const results = [];
let primaryConsole;
function run(...args) {
  const r = spawnSync(browser, args, { encoding: "utf8", timeout: 65000 });
  if (r.error || r.status !== 0)
    throw Error(`${args[0]}: ${r.error || r.stderr || r.stdout}`);
  return r.stdout
    .split("\n")
    .filter((l) => !l.startsWith("---"))
    .join("\n")
    .trim();
}
function js(code) {
  return JSON.parse(run("js", `JSON.stringify(${code})`));
}
function check(name, code) {
  assert.equal(js(code), true, name);
  results.push(name);
  console.log(`PASS ${name}`);
}
function pause(ms = 150) {
  run("js", `new Promise(resolve=>setTimeout(resolve,${ms}))`);
}
function wait(code) {
  for (let i = 0; i < 40; i++) {
    if (js(code)) return;
    pause();
  }
  throw Error(`Timed out: ${code}`);
}
function shot(name, top = 0) {
  run("js", `window.scrollTo(0,${top})`);
  const capture = JSON.parse(
    run("cdp", "Page.captureScreenshot", JSON.stringify({ format: "png" })),
  );
  fs.writeFileSync(
    path.join(dir, name + ".png"),
    Buffer.from(capture.data, "base64"),
  );
}
function metrics() {
  return js(`(()=>{
    const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom}};
    const font=s=>getComputedStyle(document.querySelector(s)).fontSize;
    return {viewport:[innerWidth,innerHeight],zoom:visualViewport.scale,dpr:devicePixelRatio,
      rootZoom:getComputedStyle(document.documentElement).zoom,rootFont:getComputedStyle(document.documentElement).fontSize,
      page:rect('.investigation-page'),grid:rect('.investigation-grid'),video:rect('video'),
      inspector:rect('.inspector'),timeline:rect('.unified-timeline'),
      descriptionFont:font('.evidence-list p'),timestampFont:font('.evidence-list small'),
      pageMaxWidth:getComputedStyle(document.querySelector('.investigation-page')).maxWidth,
      evidenceOverflow:getComputedStyle(document.querySelector('.evidence-list')).overflowY};
  })()`);
}
run("console", "--clear");
for (const [width, height] of [
  [1440, 900],
  [1920, 1080],
]) {
  run("viewport", `${width}x${height}`, "--scale", "1");
  run("goto", base + "/#ep010");
  run("press", "Control+0");
  wait("document.querySelector(`video`)?.readyState>=2");
  run("click", ".evidence-list > button:nth-child(3)");
  wait("Math.abs(document.querySelector(`video`).currentTime-44.5)<.06");
  check(
    `${width}x${height}: 100% zoom and expected CSS viewport`,
    `innerWidth===${width} && innerHeight===${height} && visualViewport.scale===1 && devicePixelRatio===1 && getComputedStyle(document.documentElement).zoom==='1'`,
  );
  run("js", "window.scrollTo(0,0)");
  fs.writeFileSync(
    path.join(
      dir,
      `${mode === "baseline" ? "before" : "after"}-${width}-metrics.json`,
    ),
    JSON.stringify(metrics(), null, 2),
  );
  shot(`${mode === "baseline" ? "before" : "after"}-${width}x${height}`);
  if (mode === "baseline") continue;
  check(
    `${width}: one shared timeline`,
    "document.querySelectorAll(`input[type=range]`).length===1",
  );
  check(
    `${width}: task outcome is separate from observation provenance`,
    "document.querySelector(`[data-testid=task-outcome]`).textContent.includes(`uncertain`) && !document.querySelector(`[data-testid=task-outcome]`).classList.contains(`observed`)",
  );
  run("click", ".inspector-tabs button:nth-child(2)");
  run("click", ".model-explanation summary");
  check(
    `${width}: historical model citations remain qualified`,
    "document.querySelector(`.model-explanation`).open && document.querySelector(`.model-context`).textContent.includes(`not establish task success`) && document.querySelectorAll(`.model-explanation .claim-links button`).length>0",
  );
  const citation = js(
    "document.querySelector(`.model-explanation .claim-links button`).textContent.trim().split(/\\s/)[0]",
  );
  run(
    "click",
    ".model-explanation article:first-of-type .claim-links button:first-child",
  );
  check(
    `${width}: historical citation selects its original catalog record`,
    `document.querySelector('.source-detail .eyebrow').textContent.includes(${JSON.stringify(citation)})`,
  );
  run("click", ".evidence-list > button:nth-child(3)");
  wait("Math.abs(document.querySelector(`video`).currentTime-44.5)<.06");
  run("js", "window.scrollTo(0,0)");
  check(
    `${width}: selected evidence visible above list`,
    "document.querySelector(`.source-detail`).getBoundingClientRect().bottom<document.querySelector(`.evidence-list`).getBoundingClientRect().top",
  );
  check(
    `${width}: readable evidence and timestamps`,
    "parseFloat(getComputedStyle(document.querySelector(`.evidence-list p`)).fontSize)>=15 && parseFloat(getComputedStyle(document.querySelector(`.evidence-list small`)).fontSize)>=13",
  );
  check(
    `${width}: inspector has no independent list scroll`,
    "getComputedStyle(document.querySelector(`.evidence-list`)).overflowY===`visible`",
  );
  check(
    `${width}: evidence selects matching camera time`,
    "document.querySelector(`input[type=range]`).value===`44.5` && Math.abs(document.querySelector(`video`).currentTime-44.5)<.06",
  );
  run("click", ".timeline-events button:nth-child(2)");
  check(
    `${width}: labeled event seeks directly`,
    "document.querySelector(`input[type=range]`).value===`44.5`",
  );
  run("click", ".timeline-marker:first-of-type");
  wait("Math.abs(document.querySelector(`video`).currentTime-43.1)<.06");
  check(
    `${width}: numbered plot marker seeks directly`,
    "document.querySelector(`input[type=range]`).value===`43.1`",
  );
  run("click", ".timeline-events button:nth-child(2)");
  check(
    `${width}: event targets at least 44px`,
    "[...document.querySelectorAll(`.timeline-events button`)].every(b=>b.getBoundingClientRect().height>=44)",
  );
  const timelineTop = js(
    "document.querySelector(`.unified-timeline`).getBoundingClientRect().top+scrollY-32",
  );
  shot(`after-timeline-${width}x${height}`, timelineTop);
  check(
    `${width}: selected evidence stays visible beside timeline`,
    "document.querySelector(`.source-detail`).getBoundingClientRect().top>=0 && document.querySelector(`.source-detail`).getBoundingClientRect().bottom<innerHeight",
  );
  run("click", ".source-detail details summary");
  check(
    `${width}: exact technical summary available`,
    "document.querySelector(`.source-detail details`).open && document.querySelector(`.source-detail`).textContent.includes(`proprio:observation.state[gripper]`)",
  );
  run("click", ".source-detail details summary");
  run("click", "input[type=range]");
  wait(
    "Math.abs(document.querySelector(`video`).currentTime-Number(document.querySelector(`input[type=range]`).value))<.06",
  );
  check(
    `${width}: manual timeline seeking follows camera`,
    "Math.abs(document.querySelector(`video`).currentTime-Number(document.querySelector(`input[type=range]`).value))<.06",
  );
  run("click", ".evidence-seek");
  wait("Math.abs(document.querySelector(`video`).currentTime-44.5)<.06");
  check(
    `${width}: selected reference seeks directly`,
    "document.querySelector(`input[type=range]`).value===`44.5`",
  );
  run("click", ".camera-stage .space-y-3 button:nth-of-type(2)");
  wait(
    "document.querySelector(`video`).readyState>=2 && Math.abs(document.querySelector(`video`).currentTime-44.5)<.06",
  );
  check(
    `${width}: SAM overlay preserves camera time`,
    "document.querySelector(`video`).getAttribute(`src`).endsWith(`/overlay.mp4`) && Math.abs(document.querySelector(`video`).currentTime-44.5)<.06",
  );
  shot(`after-sam-${width}x${height}`);
  run("click", ".play-button");
  pause(500);
  run("click", ".play-button");
  check(
    `${width}: playback advances with camera in sync`,
    "Number(document.querySelector(`input[type=range]`).value)>44.7 && Math.abs(document.querySelector(`video`).currentTime-Number(document.querySelector(`input[type=range]`).value))<.12",
  );
}
if (mode !== "baseline") {
  for (const [width, height] of [
    [1024, 900],
    [768, 1024],
    [390, 844],
  ]) {
    run("viewport", `${width}x${height}`);
    run("goto", base + "/#ep010");
    wait("document.querySelector(`video`)?.readyState>=2");
    check(
      `${width}: responsive layout has no horizontal overflow`,
      "document.documentElement.scrollWidth<=innerWidth",
    );
    shot(`after-responsive-${width}`);
  }
  run("viewport", "1440x900");
  primaryConsole = run("console", "--errors");
  run("goto", base + "/#ep010");
  run("click", "[data-testid=open-advanced-robotics-viewer]");
  wait(
    "!!document.querySelector(`[data-testid=advanced-robotics-overlay][role=dialog]`)",
  );
  check(
    "Rerun becomes ready with primary view retained",
    "!!document.querySelector(`.investigation-grid`) && location.hash===`#rerun-ep010`",
  );
  // Recording readiness precedes the first decoded video frame in Rerun.
  pause(3000);
  shot("after-rerun-1440x900");
  run(
    "js",
    "[...document.querySelectorAll(`button`)].find(b=>b.textContent.trim()===`Return to investigation`).click()",
  );
  wait(
    "location.hash===`#ep010` && !document.querySelector(`[data-testid=advanced-robotics-overlay]`)",
  );
  check(
    "Rerun returns to usable investigation",
    "!!document.querySelector(`.inspector`) && !document.querySelector(`.investigation-grid`).closest(`[inert]`)",
  );
}
fs.writeFileSync(
  path.join(dir, mode + "-checks.json"),
  JSON.stringify(
    { results, primaryConsole, console: run("console", "--errors") },
    null,
    2,
  ),
);
console.log(`${results.length} checks passed (${mode}).`);
