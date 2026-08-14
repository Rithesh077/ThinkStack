/**
 * Whether the first-run model note has been shown yet.
 *
 * A separate file from the component purely so the component file exports
 * only a component: React Fast Refresh cannot hot-reload a module that mixes
 * components with plain functions, and the lint rule that enforces this is the
 * reason this module exists.
 */

const SEEN_KEY = 'thinkstack.firstRun.modelNote';

/** Record that the note has been seen, so it never returns. */
export function markFirstRunNoteSeen() {
  try {
    localStorage.setItem(SEEN_KEY, new Date().toISOString());
  } catch {
    /* private mode: worst case it is shown once more */
  }
}

/** Has it already been shown on this install? */
export function firstRunNoteSeen() {
  try {
    return Boolean(localStorage.getItem(SEEN_KEY));
  } catch {
    return false;   // storage unavailable -> show it; a repeat beats silence
  }
}

const TOUR_KEY = 'thinkstack.library.tour';

/**
 * Should Library open its "what's here" tour expanded?
 *
 * Only for someone who has never run this app. An existing user who updates
 * has already found LitGraph and Scribe, and greeting them with an
 * introduction to their own workspace reads as a regression -- which is why
 * this asks `firstRunNoteSeen()` rather than defaulting to open. That flag is
 * set the moment the first-run banner is dismissed, so the two agree on who
 * is new without keeping separate records of it.
 *
 * Once the user opens or closes it themselves, that choice wins forever.
 */
export function libraryTourOpen() {
  try {
    const chosen = localStorage.getItem(TOUR_KEY);
    if (chosen !== null) return chosen === 'true';
    return !firstRunNoteSeen();
  } catch {
    return false;
  }
}

export function setLibraryTourOpen(open) {
  try {
    localStorage.setItem(TOUR_KEY, String(open));
  } catch {
    /* private mode: the tour just forgets between launches */
  }
}
