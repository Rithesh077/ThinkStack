/**
 * Colour the app has earned.
 *
 * ThinkStack ships greyscale. Four pigments exist, and each is granted by the
 * one thing it names -- ochre when a paper is first ingested, moss when an
 * analysis first runs, slate when the map is first opened, and the red pen
 * when a gap is first found. Earning is permanent: deleting every paper does
 * not take the colour back, because what was earned was the act, not the row.
 *
 * The whole earned set is written into a single `data-earned` attribute on
 * <html> as space-separated words, which index.css matches with `~=`. That is
 * the entire mechanism -- no context, no provider, no re-render. A pigment
 * arriving is one attribute write, and every var(--mark) in the app follows.
 *
 * TWO CONCEPTS LIVE HERE, and keeping them apart is the whole design:
 *
 *   the RECORD  -- earned(), what this install actually did. Append-only.
 *   the LENS    -- mode(), how much of it the reader wants painted.
 *
 * Some readers do not want to be made to wait for their own interface, and
 * some want the grey notebook and want to keep it. So the mechanic is offered
 * rather than imposed: `full` inks all four now, `grey` never paints any. But
 * a mode is a lens over the record and never a rewrite of it -- take the full
 * set on day one, switch back to `earn` a month later, and you get exactly the
 * pigments you genuinely earned in the meantime. That is what lets "earning is
 * permanent" stay true in the presence of a choice, instead of the choice
 * quietly becoming a way to fake it.
 *
 * visible() is the only thing the DOM ever sees.
 *
 * Kept out of the component tree for the same reason as utils/firstRun.js:
 * React Fast Refresh cannot hot-reload a module mixing components with plain
 * functions.
 */

const EARNED_KEY = 'thinkstack.pigments';
const MODE_KEY = 'thinkstack.pigments.mode';

/**
 * What we know when localStorage does not work.
 *
 * Private browsing, a locked-down webview, a full disk: setItem throws and the
 * record cannot persist. That is survivable -- the colour is correct for as
 * long as the session lasts, and a pigment that appears and is later forgotten
 * beats one that never appears. But it only works if reads stop going back to
 * the storage that just refused the write, so once a write fails this module
 * keeps the record in memory and reads from there for the rest of the session.
 */
const memory = { record: null, mode: null };

/** The only names that mean anything. Anything else is ignored. */
export const PIGMENTS = ['ochre', 'moss', 'slate', 'mark'];

/** Milestone -> pigment, so call sites name the event and not the colour. */
export const EARNED_BY = {
  paperIngested: 'ochre',
  analysisRun: 'moss',
  graphOpened: 'slate',
  gapFound: 'mark',
};

/** What each pigment cost, in the reader's terms. Used by the margin note. */
export const EARNED_FOR = {
  ochre: 'reading your first paper',
  moss: 'running your first analysis',
  slate: 'opening the map',
  mark: 'finding your first gap',
};

/** The three lenses. `earn` is the default and the one the app was built for. */
export const MODES = ['earn', 'full', 'grey'];

/** Fired on window the moment a pigment is genuinely earned. Detail: its name. */
export const PIGMENT_EARNED = 'thinkstack:pigment-earned';

/** The set earned so far, oldest first. The record. Never throws. */
export function earned() {
  if (memory.record) return [...memory.record];
  let raw = '';
  try {
    raw = localStorage.getItem(EARNED_KEY) || '';
  } catch {
    /* storage unavailable: the app is simply grey this run */
  }
  return raw.split(' ').filter((p) => PIGMENTS.includes(p));
}

/** The lens in force. Never throws. */
export function mode() {
  if (memory.mode) return memory.mode;
  let raw = '';
  try {
    raw = localStorage.getItem(MODE_KEY) || '';
  } catch {
    /* storage unavailable: fall back to the behaviour the app was built for */
  }
  return MODES.includes(raw) ? raw : 'earn';
}

/**
 * What actually reaches the DOM: the record seen through the lens.
 *
 * Note `grey` returns nothing while earn() keeps growing underneath it. A
 * reader in grey mode is still earning; they have just asked not to be shown.
 */
export function visible() {
  switch (mode()) {
    case 'full': return [...PIGMENTS];
    case 'grey': return [];
    default: return earned();
  }
}

/**
 * Push the visible set onto <html> so the stylesheet can see it.
 *
 * Safe to call on every load; it is idempotent and writes one attribute. This
 * is the only writer of data-earned in the app.
 */
export function applyEarned() {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-earned', visible().join(' '));
}

/**
 * Change the lens, persist it, and repaint. Unknown names are no-ops.
 *
 * Never touches the record, which is the point.
 */
export function setMode(next) {
  if (!MODES.includes(next)) return mode();
  try {
    localStorage.setItem(MODE_KEY, next);
  } catch {
    memory.mode = next;
  }
  applyEarned();
  return next;
}

/**
 * Grant a pigment, persist it, and paint it.
 *
 * Returns true only when this call is what earned it -- so a caller can react
 * to the moment (a note, a sound) without having to track it separately.
 * Unknown names and already-earned names are no-ops.
 */
export function earn(pigment) {
  if (!PIGMENTS.includes(pigment)) return false;
  const set = earned();
  if (set.includes(pigment)) return false;

  set.push(pigment);
  try {
    localStorage.setItem(EARNED_KEY, set.join(' '));
  } catch {
    // Storage is gone, so this will not survive a reload. Hold the record in
    // memory so the rest of the session still reads it back.
    memory.record = set;
  }
  // Through the lens, not straight from the record: in `grey` this writes the
  // record forward and paints nothing, which is exactly what grey means.
  applyEarned();

  // The ceremony fires from here rather than from the four call sites, so a
  // fifth milestone added later cannot forget to announce itself. One event,
  // once per pigment per install, and only when there is something to see.
  if (typeof window !== 'undefined' && shouldAnnounce()) {
    window.dispatchEvent(new CustomEvent(PIGMENT_EARNED, { detail: pigment }));
  }
  return true;
}

/**
 * Should the arrival of `pigment` be announced?
 *
 * Only in `earn` mode. In `full` the pigment was already inked, so there is
 * nothing to announce; in `grey` the reader has asked not to be shown. The
 * caller has already established that this call is what earned it.
 */
export function shouldAnnounce() {
  return mode() === 'earn';
}

/** Has this pigment been earned? */
export function hasEarned(pigment) {
  return earned().includes(pigment);
}

/**
 * Grant, in one write, everything a library proves was already earned.
 *
 * An install that predates this feature has a full library and an empty
 * earned set, and showing that user a grey app would read as a downgrade
 * rather than a beginning. Runs only while nothing has been earned at all,
 * so it can never fight a real milestone.
 *
 * Counts come from what the caller already fetched; this does no I/O.
 */
export function backfill({ papers = 0, analyses = 0, gaps = 0 } = {}) {
  if (earned().length > 0) return [];

  const granted = [];
  // A library with papers in it has been through ingest and the map.
  if (papers > 0) granted.push('ochre', 'slate');
  if (analyses > 0) granted.push('moss');
  if (gaps > 0) granted.push('mark');

  for (const p of granted) earn(p);
  return granted;
}

/** Test seam: forget everything, record and lens both. Not reachable from the UI. */
export function __resetPigments() {
  memory.record = null;
  memory.mode = null;
  try {
    localStorage.removeItem(EARNED_KEY);
    localStorage.removeItem(MODE_KEY);
  } catch {
    /* nothing to forget */
  }
  if (typeof document !== 'undefined') {
    document.documentElement.removeAttribute('data-earned');
  }
}
