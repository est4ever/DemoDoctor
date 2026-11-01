// @vitest-environment jsdom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { readFileSync } from "node:fs";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "../App";
import { PANEL_STORAGE_KEY } from "../lib/usePanelLayout";
vi.mock("./VideoPane", () => ({ VideoPane: ({t}: {t: number}) => <output data-testid="time">{t}</output> }));
const json = (path: string) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));
let root: Root, host: HTMLDivElement;
const captureKeys = ["setPointerCapture", "hasPointerCapture", "releasePointerCapture"] as const;
const captureDescriptors = captureKeys.map(key => Object.getOwnPropertyDescriptor(HTMLElement.prototype, key));
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  localStorage.clear(); sessionStorage.clear();
  Object.defineProperty(window, "innerWidth", {value: 1920, configurable: true});
  Object.defineProperty(window, "innerHeight", {value: 1080, configurable: true});
  history.replaceState({}, "", "/#ep010");
  host = document.createElement("div"); document.body.append(host); root = createRoot(host);
  vi.stubGlobal("fetch", vi.fn(async (url: string) => new Response(JSON.stringify(json(`../../public/data/ep010/${url.split('/').pop()}`)), {status: 200})));
});
afterEach(async () => {
  await act(async () => root.unmount()); host.remove(); localStorage.clear(); vi.restoreAllMocks(); vi.unstubAllGlobals();
  captureKeys.forEach((key, i) => {
    const descriptor = captureDescriptors[i];
    if (descriptor) Object.defineProperty(HTMLElement.prototype, key, descriptor);
    else delete (HTMLElement.prototype as unknown as Record<string, unknown>)[key];
  });
});
async function load() { await act(async () => root.render(<App />)); }
const button = (name: string) => host.querySelector<HTMLButtonElement>(`button[aria-label="${name}"]`)!;
async function click(name: string) { await act(async () => button(name).click()); }
const divider = (name: string) => host.querySelector<HTMLElement>(`[role="separator"][aria-label="${name}"]`)!;
async function key(element: HTMLElement, key: string) { await act(async () => element.dispatchEvent(new KeyboardEvent("keydown", {key, code: key, bubbles: true}))); }
const time = () => host.querySelector('[data-testid="time"]')!.textContent;

it("collapses without unmounting evidence, losing source expansion, scrolling or seeking", async () => {
  await load();
  const item = [...host.querySelectorAll<HTMLButtonElement>('.evidence-list button')].find(b => b.querySelector('.evidence-id')?.textContent === 'E2')!;
  await act(async () => item.click());
  const source = host.querySelector<HTMLDetailsElement>('#evidence-source-details')!;
  const scroll = host.querySelector<HTMLElement>('.inspector-scroll')!; scroll.scrollTop = 123;
  const before = time();
  await click("Collapse evidence inspector");
  expect(host.querySelector('#evidence-inspector')?.getAttribute('aria-hidden')).toBe('true');
  await click("Expand evidence inspector");
  expect(host.querySelector('#evidence-source-details')).toBe(source);
  expect(source.open).toBe(true); expect(scroll.scrollTop).toBe(123); expect(time()).toBe(before);
  expect(document.activeElement).toBe(button("Collapse evidence inspector"));
});

it("supports keyboard resizing without frame stepping and persists independent collapsed states", async () => {
  await load(); const before = time();
  await key(divider("Resize navigation"), "End");
  await key(divider("Resize evidence inspector"), "ArrowLeft");
  expect(divider("Resize navigation").getAttribute('aria-valuenow')).toBe('320');
  expect(divider("Resize evidence inspector").getAttribute('aria-valuenow')).toBe('416');
  expect(time()).toBe(before);
  await click("Collapse navigation"); await click("Collapse evidence inspector");
  expect(JSON.parse(localStorage.getItem(PANEL_STORAGE_KEY)!)).toMatchObject({leftWidth: 320, rightWidth: 416, leftCollapsed: true, rightCollapsed: true});
  await act(async () => root.unmount()); root = createRoot(host); await load();
  expect(button("Expand navigation")).not.toBeNull(); expect(button("Expand evidence inspector")).not.toBeNull();
  await click("Expand navigation"); await click("Expand evidence inspector");
  expect(divider("Resize evidence inspector").getAttribute('aria-valuenow')).toBe('416');
});

it("drags both dividers and resets by double-click or the global reset control", async () => {
  HTMLElement.prototype.setPointerCapture = vi.fn();
  HTMLElement.prototype.hasPointerCapture = vi.fn(() => true);
  HTMLElement.prototype.releasePointerCapture = vi.fn();
  await load(); const before = time();
  const right = divider("Resize evidence inspector");
  await act(async () => { right.dispatchEvent(new MouseEvent("pointerdown", {button: 0, clientX: 800, bubbles: true}));
    right.dispatchEvent(new MouseEvent("pointermove", {clientX: 700, bubbles: true}));
    right.dispatchEvent(new MouseEvent("pointerup", {bubbles: true})); });
  expect(right.getAttribute('aria-valuenow')).toBe('500');
  const left = divider("Resize navigation");
  await act(async () => { left.dispatchEvent(new MouseEvent("pointerdown", {button: 0, clientX: 222, bubbles: true}));
    left.dispatchEvent(new MouseEvent("pointermove", {clientX: 282, bubbles: true}));
    left.dispatchEvent(new MouseEvent("pointerup", {bubbles: true})); });
  expect(left.getAttribute('aria-valuenow')).toBe('282');
  await act(async () => right.dispatchEvent(new MouseEvent("dblclick", {bubbles: true})));
  expect(right.getAttribute('aria-valuenow')).toBe('400'); expect(time()).toBe(before);
  await click("Reset panel layout"); expect(left.getAttribute('aria-valuenow')).toBe('222');
});

it("uses a closable narrow drawer and restores desktop preferences after resizing", async () => {
  await load();
  await act(async () => { Object.defineProperty(window, "innerWidth", {value: 375}); window.dispatchEvent(new Event('resize')); });
  expect(button("Expand evidence inspector")).not.toBeNull();
  await click("Expand evidence inspector");
  expect(host.querySelector('#evidence-inspector')?.getAttribute('aria-modal')).toBe('true');
  await key(button("Collapse evidence inspector"), "Escape");
  expect(document.activeElement).toBe(button("Expand evidence inspector"));
  await act(async () => { Object.defineProperty(window, "innerWidth", {value: 1366}); window.dispatchEvent(new Event('resize')); });
  expect(divider("Resize evidence inspector").getAttribute('aria-valuenow')).toBe('400');
  expect(JSON.parse(localStorage.getItem(PANEL_STORAGE_KEY)!).rightCollapsed).toBe(false);
});
