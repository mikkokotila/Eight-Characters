// Selected Lucide 1.53.0 icons, ISC / MIT. See icons.LICENSE. No runtime dependency.
(() => {
  const paths = {
  "languages": "<path d=\"m5 8 6 6\" /> <path d=\"m4 14 6-6 2-3\" /> <path d=\"M2 5h12\" /> <path d=\"M7 2h1\" /> <path d=\"m22 22-5-10-5 10\" /> <path d=\"M14 18h6\" />",
  "orbit": "<path d=\"M20.341 6.484A10 10 0 0 1 10.266 21.85\" /> <path d=\"M3.659 17.516A10 10 0 0 1 13.74 2.152\" /> <circle cx=\"12\" cy=\"12\" r=\"3\" /> <circle cx=\"19\" cy=\"5\" r=\"2\" /> <circle cx=\"5\" cy=\"19\" r=\"2\" />",
  "layers-2": "<path d=\"M13 13.74a2 2 0 0 1-2 0L2.5 8.87a1 1 0 0 1 0-1.74L11 2.26a2 2 0 0 1 2 0l8.5 4.87a1 1 0 0 1 0 1.74z\" /> <path d=\"m20 14.285 1.5.845a1 1 0 0 1 0 1.74L13 21.74a2 2 0 0 1-2 0l-8.5-4.87a1 1 0 0 1 0-1.74l1.5-.845\" />",
  "columns-4": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M7.5 3v18\" /> <path d=\"M12 3v18\" /> <path d=\"M16.5 3v18\" />",
  "workflow": "<rect width=\"8\" height=\"8\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M7 11v4a2 2 0 0 0 2 2h4\" /> <rect width=\"8\" height=\"8\" x=\"13\" y=\"13\" rx=\"2\" />",
  "link-2": "<path d=\"M9 17H7A5 5 0 0 1 7 7h2\" /> <path d=\"M15 7h2a5 5 0 1 1 0 10h-2\" /> <line x1=\"8\" x2=\"16\" y1=\"12\" y2=\"12\" />",
  "clipboard-list": "<rect width=\"8\" height=\"4\" x=\"8\" y=\"2\" rx=\"1\" ry=\"1\" /> <path d=\"M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2\" /> <path d=\"M12 11h4\" /> <path d=\"M12 16h4\" /> <path d=\"M8 11h.01\" /> <path d=\"M8 16h.01\" />",
  "pencil": "<path d=\"M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z\" /> <path d=\"m15 5 4 4\" />",
  "square-plus": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M8 12h8\" /> <path d=\"M12 8v8\" />",
  "columns-2": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M12 3v18\" />",
  "chevron-down": "<path d=\"m6 9 6 6 6-6\" />",
  "sun-snow": "<path d=\"M10 21v-1\" /> <path d=\"M10 4V3\" /> <path d=\"M10 9a3 3 0 0 0 0 6\" /> <path d=\"m14 20 1.25-2.5L18 18\" /> <path d=\"m14 4 1.25 2.5L18 6\" /> <path d=\"m17 21-3-6 1.5-3H22\" /> <path d=\"m17 3-3 6 1.5 3\" /> <path d=\"M2 12h1\" /> <path d=\"m20 10-1.5 2 1.5 2\" /> <path d=\"m3.64 18.36.7-.7\" /> <path d=\"m4.34 6.34-.7-.7\" />",
  "sprout": "<path d=\"M14 9.536V7a4 4 0 0 1 4-4h1.5a.5.5 0 0 1 .5.5V5a4 4 0 0 1-4 4 4 4 0 0 0-4 4c0 2 1 3 1 5a5 5 0 0 1-1 3\" /> <path d=\"M4 9a5 5 0 0 1 8 4 5 5 0 0 1-8-4\" /> <path d=\"M5 21h14\" />",
  "users-round": "<path d=\"M18 21a8 8 0 0 0-16 0\" /> <circle cx=\"10\" cy=\"8\" r=\"5\" /> <path d=\"M22 20c0-3.37-2-6.5-4-8a5 5 0 0 0-.45-8.3\" />",
  "waypoints": "<path d=\"m10.586 5.414-5.172 5.172\" /> <path d=\"m18.586 13.414-5.172 5.172\" /> <path d=\"M6 12h12\" /> <circle cx=\"12\" cy=\"20\" r=\"2\" /> <circle cx=\"12\" cy=\"4\" r=\"2\" /> <circle cx=\"20\" cy=\"12\" r=\"2\" /> <circle cx=\"4\" cy=\"12\" r=\"2\" />",
  "x": "<path d=\"M18 6 6 18\" /> <path d=\"m6 6 12 12\" />",
  "chevron-right": "<path d=\"m9 18 6-6-6-6\" />",
  "arrow-up-right": "<path d=\"M7 7h10v10\" /> <path d=\"M7 17 17 7\" />",
  "arrow-left": "<path d=\"m12 19-7-7 7-7\" /> <path d=\"M19 12H5\" />",
  "circle-dot": "<circle cx=\"12\" cy=\"12\" r=\"1\" /> <circle cx=\"12\" cy=\"12\" r=\"10\" />",
  "calendar-range": "<rect x=\"3\" y=\"3\" width=\"18\" height=\"18\" rx=\"2\" /> <path d=\"M16 2v3\" /> <path d=\"M3 9h18\" /> <path d=\"M8 2v3\" /> <path d=\"M17 13h-6\" /> <path d=\"M13 17H7\" /> <path d=\"M7 13h.01\" /> <path d=\"M17 17h.01\" />",
  "chevron-left": "<path d=\"m15 18-6-6 6-6\" />",
  "calendar-check": "<path d=\"M8 2v3\" /> <path d=\"M16 2v3\" /> <rect x=\"3\" y=\"3\" width=\"18\" height=\"18\" rx=\"2\" /> <path d=\"M3 9h18\" /> <path d=\"m9 15 2 2 4-4\" />",
  "panel-top": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M3 9h18\" />",
  "panel-bottom": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M3 15h18\" />",
  "clock-12": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M12 6v6\" />",
  "clock-11": "<circle cx=\"12\" cy=\"12\" r=\"10\" /> <path d=\"M12 6v6l-2-4\" />",
  "panel-left": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M9 3v18\" />",
  "panel-right": "<rect width=\"18\" height=\"18\" x=\"3\" y=\"3\" rx=\"2\" /> <path d=\"M15 3v18\" />",
  "arrow-left-right": "<path d=\"M8 3 4 7l4 4\" /> <path d=\"M4 7h16\" /> <path d=\"m16 21 4-4-4-4\" /> <path d=\"M20 17H4\" />",
  "keyboard": "<path d=\"M10 8h.01\" /> <path d=\"M12 12h.01\" /> <path d=\"M14 8h.01\" /> <path d=\"M16 12h.01\" /> <path d=\"M18 8h.01\" /> <path d=\"M6 8h.01\" /> <path d=\"M7 16h10\" /> <path d=\"M8 12h.01\" /> <rect width=\"20\" height=\"16\" x=\"2\" y=\"4\" rx=\"2\" />",
  "command": "<path d=\"M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3\" />",
  "printer": "<path d=\"M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2\" /> <path d=\"M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6\" /> <rect x=\"6\" y=\"14\" width=\"12\" height=\"8\" rx=\"1\" />"
};
  const markup = (name, extraClass = '') => {
    if (!Object.hasOwn(paths, name)) throw new Error(`Unknown control icon: ${name}.`);
    return `<svg class="control-icon ${extraClass}" data-control-icon="${name}" aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${paths[name]}</svg>`;
  };
  window.EC_ICONS = { markup };
})();
