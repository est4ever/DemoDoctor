import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const appSrc = readFileSync(join(here, "App.tsx"), "utf8");

/**
 * Regression: an early `return <Rerun…>` before later hooks blanked #root when
 * switching #rerun-ep010 ↔ #ep010 (Rules of Hooks violation).
 */
describe("App.tsx Rerun route / hooks safety", () => {
  it("does not statically import the Rerun web-viewer package", () => {
    expect(appSrc).not.toMatch(/from\s+["']@rerun-io\/web-viewer/);
    expect(appSrc).not.toMatch(/from\s+["']@rerun-io\/web-viewer-react/);
    expect(appSrc).toMatch(/lazy\s*\(\s*\(\)\s*=>\s*import\(/);
    expect(appSrc).toMatch(/AdvancedRoboticsViewer/);
  });

  it("keeps the primary investigation mounted while the advanced viewer loads", () => {
    expect(appSrc).toMatch(/advanced-robotics-overlay/);
    expect(appSrc).toMatch(/Loading Advanced Robotics Viewer/);
    expect(appSrc).toMatch(/Return to investigation/);
    // Must not early-return the whole app for the Rerun hash (overlay instead).
    expect(appSrc).not.toMatch(
      /if\s*\(\s*rerunEp010\s*\)\s*\{\s*return\s+<\s*Rerun/,
    );
    expect(appSrc).not.toMatch(
      /if\s*\(\s*rerunEp010\s*\)\s*\{\s*return\s+<\s*AdvancedRoboticsViewer/,
    );
  });

  it("declares App hooks before the primary app-shell JSX return", () => {
    const appFnStart = appSrc.indexOf("export default function App");
    expect(appFnStart).toBeGreaterThanOrEqual(0);
    const appFn = appSrc.slice(appFnStart);
    const shellReturn = appFn.search(
      /return\s*\(\s*<div className="app-shell">/,
    );
    expect(shellReturn).toBeGreaterThan(0);

    const beforeShell = appFn.slice(0, shellReturn);
    const afterShell = appFn.slice(shellReturn);

    expect(beforeShell).toMatch(/\buseSharedPlayback\s*\(/);
    expect(beforeShell).toMatch(/\buseEffect\s*\(/);
    expect(
      [...beforeShell.matchAll(/\buse(Effect|Memo|Callback|State|SharedPlayback)\s*(\(|<)/g)]
        .length,
    ).toBeGreaterThan(5);

    // No additional hook declarations after the shell return (Rules of Hooks).
    expect(afterShell).not.toMatch(
      /^\s*(const|let).*\buse(Effect|Memo|Callback|State|SharedPlayback)\s*(\(|<)/m,
    );
  });

  it("exposes Advanced Robotics Viewer from the investigation workspace for ep010", () => {
    expect(appSrc).toMatch(/Advanced Robotics Viewer/);
    expect(appSrc).toMatch(/open-advanced-robotics-viewer/);
    expect(appSrc).toMatch(/RERUN_EP010_HASH/);
  });
});
