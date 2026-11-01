// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { DEFAULT_PANELS, PANEL_STORAGE_KEY, panelBounds, readPanelPreferences } from "./usePanelLayout";
afterEach(() => { localStorage.clear(); vi.restoreAllMocks(); });

it("restores only valid preferences and clamps untrusted saved widths", () => {
  localStorage.setItem(PANEL_STORAGE_KEY, '{"leftWidth":99999,"rightWidth":-20,"leftCollapsed":true,"rightCollapsed":"false"}');
  expect(readPanelPreferences()).toEqual({leftWidth: 320, rightWidth: 320, leftCollapsed: true, rightCollapsed: false});
  for (const invalid of ["broken JSON", "null", '{"leftWidth":1e309,"rightWidth":"600"}']) {
    localStorage.setItem(PANEL_STORAGE_KEY, invalid);
    expect(readPanelPreferences()).toEqual(DEFAULT_PANELS);
  }
});

it("keeps a usable camera column at desktop limits, including saved maximum widths", () => {
  for (const width of [1051, 1366, 1440, 1920]) for (const leftCollapsed of [true, false]) for (const rightCollapsed of [true, false]) {
    const bounds = panelBounds({...DEFAULT_PANELS, leftWidth: 320, rightWidth: 600, leftCollapsed, rightCollapsed}, width, 768);
    expect(width - bounds.leftOffset - 60 - (rightCollapsed ? 44 : bounds.rightWidth)).toBeGreaterThanOrEqual(440);
    expect(bounds.rightWidth).toBeGreaterThanOrEqual(320);
    expect(bounds.rightWidth).toBeLessThanOrEqual(600);
  }
});

it("uses viewport-bounded drawers rather than narrow desktop columns", () => {
  const bounds = panelBounds(DEFAULT_PANELS, 375, 812);
  expect(bounds.desktop).toBe(false);
  expect(bounds.leftOffset).toBe(56);
  expect(bounds.rightWidth).toBe(295);
  expect(panelBounds(DEFAULT_PANELS, 1920, 600).desktop).toBe(false);
});

it("survives unavailable browser storage", () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Blocked"); });
  expect(readPanelPreferences()).toEqual(DEFAULT_PANELS);
});
