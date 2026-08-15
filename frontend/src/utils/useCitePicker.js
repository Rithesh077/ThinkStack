/**
 * Citing a paper without leaving the sentence you are writing.
 *
 * Type `cite` in the editor and the library drops down under the caret; keep
 * typing and it filters; press Enter and the word becomes `\cite{key}` with
 * the entry written into the project's references.bib.
 *
 * The trigger is the bare word, not a keystroke, because the author is already
 * typing when they decide to cite. Nothing is committed until they choose:
 * dismiss the list and `cite` is still just a word, and a word compiles.
 *
 * Numbering is not tracked here, or anywhere. BibTeX renumbers every `\cite`
 * on each recompile, which is the whole reason to emit keys rather than the
 * `[3]` the author can see.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { papersApi } from './api';
import { caretCoords } from './caret';

// `cite` preceded by anything that is not a letter or a backslash: mid-word
// (`recite`) is not a trigger, and `\cite` is one the author already finished.
// The tail runs to the caret and is the filter query.
const TRIGGER = /(?:^|[^\\A-Za-z])cite([^\n]*)$/;

// Past this the author is writing a sentence about citing, not choosing a
// paper. The empty-result rule closes most of those sooner.
const MAX_QUERY = 48;

// Roughly what the list occupies. Used only to decide which side of the caret
// it opens on, so being a little out costs nothing.
const LIST_H = 250;
const LIST_W = 360;

/**
 * Where to draw the list, in viewport coordinates.
 *
 * Viewport and not the editor pane, because the pane sits inside
 * `overflow: hidden` -- an absolutely positioned child that runs past its
 * bottom edge is clipped away rather than scrolled to. That is what made this
 * look like a dead feature: the list rendered, with every row in it, 1382px
 * down a 1000px window.
 *
 * The caret's y is clamped into the textarea's own visible box first. A caret
 * scrolled out of sight still has a true position hundreds of pixels away, and
 * anchoring to it would put the list somewhere the author is not looking.
 */
function anchor(el, caret) {
  const box = el.getBoundingClientRect();
  const { top, left, height } = caretCoords(el, caret);

  const y = Math.min(Math.max(box.top + top, box.top), box.bottom - height);
  const x = Math.min(box.left + left, window.innerWidth - LIST_W - 8);

  // Below the line normally; above it when the caret is near the bottom of
  // the window, which is where the last paragraph of a document usually is.
  const below = window.innerHeight - (y + height);
  return below < LIST_H
    ? { left: Math.max(8, x), bottom: window.innerHeight - y, top: null }
    : { left: Math.max(8, x), top: y + height, bottom: null };
}

function matches(row, query) {
  if (!query) return true;
  const hay = `${row.title} ${(row.authors || []).join(' ')} ${row.year} ${row.key}`.toLowerCase();
  return query.toLowerCase().split(/\s+/).every((term) => hay.includes(term));
}

/**
 * Detection, positioning and keyboard for the picker.
 *
 * `applyEdit(from, to, text)` is the caller's -- this hook never touches the
 * source itself, because Scribe owns the undo buffer and the dirty flag.
 */
export default function useCitePicker({ textareaRef, source, projectId, applyEdit }) {
  // Keyed by project rather than cleared by an effect: on the render right
  // after switching projects, an effect has not run yet, and for that one
  // render the list would be the previous project's papers.
  const [cache, setCache] = useState({ projectId: null, rows: [] });
  const rows = cache.projectId === projectId ? cache.rows : [];
  const [open, setOpen] = useState(null);   // { start, query, top|bottom, left }
  // The highlighted row belongs to the query it was chosen under, so a new
  // query starts at the top without anything having to reset it.
  const [choice, setChoice] = useState({ query: null, index: 0 });
  const [busy, setBusy] = useState(false);
  // Set when the author dismisses the list, cleared when they leave the word.
  // Without it, Escape closes the picker and the very next keystroke -- still
  // inside `cite` -- reopens it.
  const dismissed = useRef(null);

  const loadRows = useCallback(async () => {
    if (!projectId) return;
    try {
      const d = await papersApi.citations(projectId);
      setCache({ projectId, rows: d.citations || [] });
    } catch {
      // an empty list reads as "nothing to cite", which is true enough
      setCache({ projectId, rows: [] });
    }
  }, [projectId]);

  /** Re-read the text around the caret and open, move or close the list. */
  const evaluate = useCallback(() => {
    const el = textareaRef.current;
    if (!el || !projectId) return setOpen(null);

    const caret = el.selectionStart;
    if (caret !== el.selectionEnd) return setOpen(null);   // a selection is not a caret

    const match = TRIGGER.exec(source.slice(0, caret));
    if (!match) {
      dismissed.current = null;
      return setOpen(null);
    }

    const query = match[1];
    const start = caret - query.length - 4;   // back over `cite` and the query

    if (dismissed.current === start) return setOpen(null);
    dismissed.current = null;

    if (query.length > MAX_QUERY) return setOpen(null);

    setOpen({ start, query, ...anchor(el, caret) });
  }, [source, projectId, textareaRef]);

  useEffect(() => { evaluate(); }, [evaluate]);

  // Fetched on first open rather than on mount: most editing sessions never
  // cite anything, and the list is only correct as of the moment it is shown.
  useEffect(() => { if (open && !rows.length) loadRows(); }, [open, rows.length, loadRows]);

  const visible = open ? rows.filter((r) => matches(r, open.query.trim())) : [];
  const active = choice.query === (open ? open.query : null) ? choice.index : 0;

  // A query that matches nothing means the author is writing prose, not
  // choosing. Closing on that is what keeps "we cite the usual sources" from
  // dragging a dropdown along under it.
  const showing = open && (visible.length > 0 || (!rows.length && !open.query.trim()));

  const insert = useCallback(async (row) => {
    const el = textareaRef.current;
    if (!el || !open || busy) return;
    const { start } = open;
    const to = el.selectionStart;

    setBusy(true);
    try {
      // The key comes back from the write, not from the row: the file is what
      // decides, and it may have been edited since the list was fetched.
      const d = await papersApi.cite(projectId, row.doc_id);
      applyEdit(start, to, d.cite);
      if (d.added) loadRows();   // the row's `cited` flag is now stale
    } catch {
      // leave the word alone; the author can try again or type it themselves
    }
    setBusy(false);
    setOpen(null);
  }, [open, busy, projectId, applyEdit, loadRows, textareaRef]);

  /** First refusal on the editor's keys. Returns true when it consumed one. */
  const onKeyDown = useCallback((e) => {
    if (!showing) return false;

    if (e.key === 'Escape') {
      dismissed.current = open.start;
      setOpen(null);
      e.preventDefault();
      return true;
    }
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      const step = e.key === 'ArrowDown' ? 1 : -1;
      setChoice({ query: open.query, index: (active + step + visible.length) % visible.length });
      e.preventDefault();
      return true;
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      if (visible[active]) {
        insert(visible[active]);
        e.preventDefault();
        return true;
      }
    }
    return false;
  }, [showing, open, visible, active, insert]);

  const onHover = useCallback(
    (index) => setChoice({ query: open ? open.query : null, index }),
    [open],
  );

  return {
    picker: showing ? {
      rows: visible,
      active,
      busy,
      top: open.top,
      bottom: open.bottom,
      left: open.left,
      onPick: insert,
      onHover,
    } : null,
    onKeyDown,
    onSelect: evaluate,
  };
}
