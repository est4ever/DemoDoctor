import { useEffect, useState } from "react";

export const PANEL_STORAGE_KEY = "demodoctor.panelLayout.v1";
export const DEFAULT_PANELS = { leftWidth: 222, rightWidth: 400, leftCollapsed: false, rightCollapsed: false };
export type PanelPreferences = typeof DEFAULT_PANELS;
const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function readPanelPreferences(): PanelPreferences {
  try {
    const value = JSON.parse(localStorage.getItem(PANEL_STORAGE_KEY) || "null");
    if (!value || typeof value !== "object") return { ...DEFAULT_PANELS };
    const width = (key: "leftWidth" | "rightWidth", min: number, max: number) =>
      typeof value[key] === "number" && Number.isFinite(value[key]) ? clamp(value[key], min, max) : DEFAULT_PANELS[key];
    return { leftWidth: width("leftWidth", 180, 320), rightWidth: width("rightWidth", 320, 600),
      leftCollapsed: value.leftCollapsed === true, rightCollapsed: value.rightCollapsed === true };
  } catch { return { ...DEFAULT_PANELS }; }
}

export function panelBounds(prefs: PanelPreferences, width: number, height: number) {
  const desktop = width >= 1051 && height >= 700;
  // 440px for the camera column, plus page padding and the grid gutter.
  const leftMax = desktop ? Math.min(320, Math.max(180, width - (prefs.rightCollapsed ? 44 : 320) - 60 - 440))
    : Math.min(320, Math.max(180, width - 32));
  const leftWidth = clamp(prefs.leftWidth, 180, leftMax);
  const leftOffset = desktop ? prefs.leftCollapsed ? 64 : leftWidth : 56;
  const rightMax = desktop ? Math.min(600, Math.max(320, width - leftOffset - 60 - 440)) : Math.max(240, Math.min(600, width - 80));
  return { desktop, leftMax, rightMax, leftWidth,
    rightWidth: clamp(prefs.rightWidth, Math.min(320, rightMax), rightMax), leftOffset };
}

export function usePanelLayout() {
  const [preferences, setPreferences] = useState(readPanelPreferences);
  const [viewport, setViewport] = useState(() => ({ width: window.innerWidth, height: window.innerHeight }));
  const [navDrawer, setNavDrawer] = useState(false);
  const [inspectorDrawer, setInspectorDrawer] = useState(false);
  const bounds = panelBounds(preferences, viewport.width, viewport.height);
  useEffect(() => {
    const resize = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);
  useEffect(() => {
    try { localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(preferences)); } catch { /* Layout still works without storage. */ }
  }, [preferences]);
  useEffect(() => { setNavDrawer(false); setInspectorDrawer(false); }, [bounds.desktop]);
  return { ...bounds, preferences, setPreferences, navDrawer, setNavDrawer, inspectorDrawer, setInspectorDrawer,
    navCollapsed: bounds.desktop ? preferences.leftCollapsed : !navDrawer,
    inspectorCollapsed: bounds.desktop ? preferences.rightCollapsed : !inspectorDrawer,
    reset: () => { setPreferences({ ...DEFAULT_PANELS }); setNavDrawer(false); setInspectorDrawer(false); } };
}
