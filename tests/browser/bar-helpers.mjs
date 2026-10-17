// The chart's and the day's bars, as a reader uses them, for any suite: nothing here
// opens a browser or an account.

// A bar action pressed as a reader presses it: in the toolbar's words it is an item of its
// bar's Actions menu, opened first; in icons, and in a comparison's frame, a button in the
// bar (toolbar.js).
export async function press(page, selector, options = {}) {
  const target = page.locator(selector);
  const menu = await target.evaluate((node) => {
    const list = node.closest('.bar-menu-items[role="menu"]');
    return list && !list.classList.contains('is-open') ? list.id : null;
  });
  if (menu !== null) await page.locator(`[aria-controls="${menu}"]`).click();
  await target.click(options);
}
