// Real-browser checks through gstack. No API submissions or paid inference.
// Run after `npm run dev -- --host 127.0.0.1 --port 5174 --strictPort`.
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
const report = path.resolve(__dirname, "../../docs/ui-review");
fs.mkdirSync(report, { recursive: true });
const checks = [];
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
function evaluate(code) {
  return JSON.parse(run("js", `JSON.stringify(${code})`));
}
function check(name, code) {
  assert.equal(evaluate(code), true, name);
  checks.push({ name, passed: true });
  console.log(`PASS ${name}`);
}
function capture(name, full = true) {
  run("js", "window.scrollTo(0,0)");
  const size = evaluate(
    "({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight})",
  );
  const params = {
    format: "png",
    captureBeyondViewport: true,
    ...(full
      ? {
          clip: {
            x: 0,
            y: 0,
            width: size.width,
            height: size.height,
            scale: 1,
          },
        }
      : {}),
  };
  const result = JSON.parse(
    run("cdp", "Page.captureScreenshot", JSON.stringify(params)),
  );
  fs.writeFileSync(
    path.join(report, name + ".png"),
    Buffer.from(result.data, "base64"),
  );
}
run("viewport", "1440x1000");
run("console", "--clear");
run("goto", base + "/");
check(
  "Home uses real footage",
  "document.querySelector(`.hero-image video`).getAttribute(`src`).includes(`/data/ep010/video.mp4`)",
);
capture("after-home");
run("click", ".hero-copy .lime-button");
check(
  "Home opens investigation",
  "!!document.querySelector(`.investigation-grid`)",
);
check(
  "One timeline slider",
  "document.querySelectorAll(`input[type=range]`).length === 1",
);
check(
  "No Rerun Wasm on initial route",
  "!performance.getEntriesByType(`resource`).some(r=>r.name.includes(`.wasm`))",
);
run("click", ".evidence-list button:nth-child(3)");
check(
  "Evidence seeks shared clock to E2",
  "document.querySelector(`input[type=range]`).value === `44.5`",
);
check(
  "Camera follows evidence time",
  "Math.abs(document.querySelector(`video`).currentTime-44.5)<.06",
);
check(
  "Source record matches E2",
  "document.querySelector(`.source-detail`).textContent.includes(`proprio:observation.state[gripper]`)",
);
run("click", 'button[aria-label="Next frame"]');
check(
  "Frame stepping advances one frame",
  "Math.abs(Number(document.querySelector(`input[type=range]`).value)-(44.5+1/30))<.001",
);
run("fill", 'input[aria-label="Search evidence"]', "no-such-evidence");
check(
  "Search has honest empty state",
  "!!document.querySelector(`.empty-state`) && !document.querySelector(`.evidence-list button`)",
);
run("fill", 'input[aria-label="Search evidence"]', " ");
run("click", ".filter-row button:nth-child(4)");
check(
  "Uncertain filter retains only uncertain records",
  "[...document.querySelectorAll(`.evidence-list .provenance`)].every(e=>e.textContent.includes(`uncertain`)) && document.querySelectorAll(`.evidence-list button`).length>0",
);
run("click", ".filter-row button:first-child");
run("click", ".inspector-tabs button:nth-child(2)");
check(
  "Findings distinguish observed and inferred",
  "document.querySelector(`.inspector-content`).textContent.includes(`Observed`) && document.querySelector(`.inspector-content`).textContent.includes(`Inferred`)",
);
run("click", ".inspector-tabs button:nth-child(3)");
check(
  "Unknowns are accessible",
  "document.querySelector(`.inspector-content`).textContent.includes(`Uncertain / not established`)",
);
run("click", ".inspector-tabs button:first-child");
capture("after-investigation");
run("click", ".camera-stage .space-y-3 button:nth-of-type(2)");
check(
  "SAM switches to frozen overlay",
  "document.querySelector(`video`).getAttribute(`src`).endsWith(`/overlay.mp4`)",
);
capture("after-sam");
run("click", ".session-list button:nth-child(3)");
check("Episode switching works", "location.hash === `#ep003`");
check(
  "New episode evidence loaded",
  "document.querySelector(`.investigation-heading`).textContent.includes(`ep003`) || document.querySelector(`.investigation-heading`).textContent.includes(`EP003`)",
);
run("click", ".rail nav button:nth-child(3)");
check(
  "Upload exposes local preview and real stages",
  "!!document.querySelector(`.upload-drop`) && !!document.querySelector(`.progress-stages`)",
);
check(
  "Dry run cannot submit without a video and service",
  "[...document.querySelectorAll(`.upload-page button`)].some(b=>b.textContent===`Prepare dry run` && b.disabled)",
);
check(
  "No paid inference switch",
  "!document.body.textContent.includes(`Disable it only`)",
);
capture("after-upload");
run(
  "upload",
  "input[type=file]",
  path.resolve(__dirname, "../public/data/ep010/video.mp4"),
);
run("js", "new Promise(resolve=>setTimeout(resolve,300))");
check(
  "Selected video decodes locally",
  "document.querySelector(`.upload-preview`).readyState >= 2",
);
check(
  "Import stages reflect decoded footage",
  "document.querySelector(`.progress-stages`).innerText.includes(`02 · Local preview Ready`) || document.querySelector(`.progress-stages`).children[1].innerText.includes(`Ready`)",
);
capture("after-upload-preview");
// Test progress with explicitly synthetic transport responses. Never call the API.
run(
  "js",
  `window.__originalFetch=window.fetch; window.fetch=async(input,options)=>{
 const url=String(input);
 if(url===\`/api/health\`) return new Response(JSON.stringify({ok:true}));
 if(url===\`/api/budget\`) return new Response(JSON.stringify({spent_usd:0,total_budget_usd:0,remaining_usd:0,per_run_budget_usd:0}));
 if(url===\`/api/analyze\`) { window.__uiDryRun=options.body.get(\`dry_run\`); window.__uiMuse=options.body.get(\`run_muse\`); return new Response(JSON.stringify({job_id:\`ui-smoke-synthetic\`})); }
 if(url===\`/api/jobs/ui-smoke-synthetic\`) return new Response(JSON.stringify({job_id:\`ui-smoke-synthetic\`,status:\`running\`,stages:[{name:\`UI test fixture: reading video\`}]}));
 return window.__originalFetch(input,options);
}; true`,
);
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Check local service`).click()",
);
run("js", "new Promise(resolve=>setTimeout(resolve,100))");
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Prepare dry run`).click()",
);
check(
  "Submission forces dry run and disables Muse",
  "window.__uiDryRun===`true` && window.__uiMuse===`false`",
);
run("js", "new Promise(resolve=>setTimeout(resolve,1700))");
check(
  "Progress displays service-reported stages",
  "document.body.innerText.includes(`UI test fixture: reading video`)",
);
capture("after-upload-progress-synthetic");
// Complete only the browser fixture; the upload view does not mount a live video.
run(
  "js",
  `window.__uploadFixture=JSON.parse(JSON.stringify({ ...${fs.readFileSync(path.resolve(__dirname, "../public/data/ep003/analysis.json"), "utf8")}, episode_key:\`ui-smoke-upload\`, title:\`SYNTHETIC UPLOAD FIXTURE\`, task_outcome:\`uncertain\`, pipeline_verdict:\`uncertain\`, dry_run:true, observed:[], inferred:[], evidence_catalog:[], factual_claims:[], timeline_markers:[], initial_seek_s:0 }));
const fixtureFetch=window.fetch;
window.fetch=async(input,options)=>{
 const url=String(input);
 if(url===\`/api/jobs/ui-smoke-synthetic\`) return new Response(JSON.stringify({job_id:\`ui-smoke-synthetic\`,status:\`completed\`,has_analysis:true}));
 if(url===\`/api/jobs/ui-smoke-synthetic/analysis\`) return new Response(JSON.stringify(window.__uploadFixture));
 if(url===\`/api/jobs/ui-smoke-synthetic/tracks\`) return new Response(\`null\`);
 return fixtureFetch(input,options);
}; true`,
);
run("js", "new Promise(resolve=>setTimeout(resolve,1700))");
check(
  "Synthetic completion reaches uploaded state",
  "document.querySelector(`.local-tag`).textContent.includes(`Uploaded footage`)",
);
run("click", ".session-list button:nth-child(3)");
run("js", "new Promise(resolve=>setTimeout(resolve,300))");
check(
  "Same-episode return restores cached analysis and footage",
  "document.querySelector(`.investigation-heading`).textContent.includes(`Dish`) && !document.querySelector(`.investigation-heading`).textContent.includes(`SYNTHETIC`) && document.querySelector(`video`).getAttribute(`src`)===`/data/ep003/video.mp4` && document.querySelector(`.local-tag`).textContent.includes(`Offline replay`)",
);
// Exercise a second completion followed by direct hash navigation.
run("click", ".rail nav button:nth-child(3)");
run(
  "upload",
  "input[type=file]",
  path.resolve(__dirname, "../public/data/ep010/video.mp4"),
);
run("js", "new Promise(resolve=>setTimeout(resolve,200))");
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Check local service`).click()",
);
run("js", "new Promise(resolve=>setTimeout(resolve,100))");
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Prepare dry run`).click()",
);
run("js", "new Promise(resolve=>setTimeout(resolve,1700))");
check(
  "Second synthetic completion reaches uploaded state",
  "document.querySelector(`.local-tag`).textContent.includes(`Uploaded footage`)",
);
run("js", "location.hash=`ep010`");
run("js", "new Promise(resolve=>setTimeout(resolve,300))");
check(
  "Hash navigation clears upload source and restores matching evidence",
  "document.querySelector(`video`).getAttribute(`src`)===`/data/ep010/video.mp4` && document.querySelector(`.local-tag`).textContent.includes(`Offline replay`) && !document.querySelector(`.investigation-heading`).textContent.includes(`SYNTHETIC`)",
);
// The overview can also be opened at the root URL with no episode hash.
run("js", "history.replaceState(null,``,location.pathname)");
run("click", ".rail nav button:first-child");
run("click", ".rail nav button:nth-child(3)");
run(
  "upload",
  "input[type=file]",
  path.resolve(__dirname, "../public/data/ep010/video.mp4"),
);
run("js", "new Promise(resolve=>setTimeout(resolve,200))");
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Check local service`).click()",
);
run("js", "new Promise(resolve=>setTimeout(resolve,100))");
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Prepare dry run`).click()",
);
run("js", "new Promise(resolve=>setTimeout(resolve,1700))");
check(
  "Root-route upload reaches uploaded state",
  "location.hash===`` && document.querySelector(`.local-tag`).textContent.includes(`Uploaded footage`)",
);
run("click", ".session-list button:first-child");
run("js", "new Promise(resolve=>setTimeout(resolve,300))");
check(
  "Root-route upload return restores cached episode with new hash",
  "location.hash===`#ep010` && document.querySelector(`video`).getAttribute(`src`)===`/data/ep010/video.mp4` && document.querySelector(`.local-tag`).textContent.includes(`Offline replay`) && !document.querySelector(`.investigation-heading`).textContent.includes(`SYNTHETIC`)",
);
const delayedStatusCode = `const previousFixtureFetch=window.fetch; window.fetch=async(input,options)=>{
 if(String(input)===\`/api/jobs/ui-smoke-synthetic\`) return new Promise(resolve=>{window.__releaseDelayedPoll=()=>resolve(new Response(JSON.stringify({job_id:\`ui-smoke-synthetic\`,status:\`completed\`,has_analysis:true})));});
 return previousFixtureFetch(input,options);
}; true`;
run("js", delayedStatusCode);
run("click", ".rail nav button:nth-child(3)");
run(
  "upload",
  "input[type=file]",
  path.resolve(__dirname, "../public/data/ep010/video.mp4"),
);
run("js", "new Promise(resolve=>setTimeout(resolve,200))");
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Check local service`).click()",
);
run("js", "new Promise(resolve=>setTimeout(resolve,100))");
run(
  "js",
  "[...document.querySelectorAll(`button`)].find(b=>b.textContent===`Prepare dry run`).click()",
);
run("js", "new Promise(resolve=>setTimeout(resolve,1700))");
check(
  "Delayed job response is held during navigation test",
  "typeof window.__releaseDelayedPoll===`function`",
);
run("click", ".session-list button:nth-child(3)");
run(
  "js",
  "window.__releaseDelayedPoll(); new Promise(resolve=>setTimeout(resolve,300))",
);
check(
  "Late upload response cannot replace cached evidence after navigation",
  "document.querySelector(`video`).getAttribute(`src`)===`/data/ep003/video.mp4` && document.querySelector(`.local-tag`).textContent.includes(`Offline replay`) && !document.querySelector(`.investigation-heading`).textContent.includes(`SYNTHETIC`)",
);
run("viewport", "390x844");
run("goto", base + "/");
check(
  "Mobile home has no horizontal overflow",
  "document.documentElement.scrollWidth <= innerWidth",
);
capture("after-mobile-home");
run("click", ".hero-copy .lime-button");
check(
  "Mobile investigation has no horizontal overflow",
  "document.documentElement.scrollWidth <= innerWidth",
);
capture("after-mobile-investigation");
run("viewport", "1440x1000");
const errors = run("console", "--errors");
fs.writeFileSync(
  path.join(report, "browser-checks.json"),
  JSON.stringify({ base, checks, console: errors }, null, 2),
);
console.log(`${checks.length} browser checks passed. Screenshots: ${report}`);
