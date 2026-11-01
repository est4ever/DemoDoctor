# Adjustable workstation panels — October 31, 2026

The navigation and evidence inspector can be collapsed independently. Navigation
becomes an icon rail with episode identifiers, accessible names, native tooltips
and the existing active-route indication. The inspector leaves a reopening control.

Drag either expanded panel's divider to resize. Keyboard users can focus a divider
and press Left/Right (16px), Shift+Left/Right (32px), Home/End (limits), or Enter
(default width). Double-click also resets that divider. Each panel has a width-reset
button; **Reset layout** restores both defaults and expanded desktop panels.

Navigation defaults to 222px (180–320px). Inspector defaults to 400px (320–600px).
Actual limits depend on available viewport space and reserve at least 440px for
the desktop camera column. Collapsed desktop controls occupy 64px and 44px.
The video keeps its original aspect ratio within the available camera area.

Preferences use the localStorage key `demodoctor.panelLayout.v1`. Invalid JSON,
non-finite/wrong-type widths and unavailable storage fall back safely. Saved
widths are clamped to both panel and viewport limits. Desktop preferences survive
episode navigation, refresh and Rerun. Narrow windows/short screens start with
compact navigation and an inspector drawer; these temporary drawers do not
overwrite the saved desktop collapse preferences. Drawer focus is contained,
Escape closes it, and background controls are inert while it is modal.

The inspector stays mounted while collapsed, with unchanged internal width and
an inert, hidden surface. Selected evidence, native details expansion and scroll
position remain intact. Panel handlers never call a seek/playback handler;
divider arrow keys stop propagation to the frame-step shortcut. Existing canvas
ResizeObserver behavior continues to map SAM overlays under object-contain.


Current separate-snapshot checks are in ../submission/VALIDATION.md.
