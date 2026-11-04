/**
 * Opening the app should land on the default city, even when what gets opened
 * is a city page: a home-screen icon saved on that page, a bookmark, a browser
 * suggestion from history, or a home-screen app coming back after a while.
 */

/** A home-screen app that was away this long counts as a fresh open. */
export const RESUME_AFTER_MS = 30 * 60 * 1000;

let firstPage = true;

/**
 * True once per page load, when this document was opened from outside the
 * site (no referrer from this site) rather than reloaded or reached by a link.
 */
export function openedFromOutside(): boolean {
  if (!firstPage) return false;
  firstPage = false;
  try {
    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (nav && nav.type !== "navigate") return false;
    if (document.referrer && new URL(document.referrer).origin === location.origin) return false;
    return true;
  } catch {
    return false;
  }
}

/** Running as an app added to the home screen (Safari or Chrome). */
export function isHomeScreenApp(): boolean {
  try {
    return (
      window.matchMedia("(display-mode: standalone)").matches ||
      (navigator as Navigator & { standalone?: boolean }).standalone === true
    );
  } catch {
    return false;
  }
}

/** For tests. */
export function resetLaunch() {
  firstPage = true;
}
