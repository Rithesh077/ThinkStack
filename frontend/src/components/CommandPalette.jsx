/**
 * One place to reach anything, from the keyboard.
 *
 * The application had exactly one shortcut -- Ctrl+Enter in Scribe -- so the
 * core loop of find a paper, open it, start writing was entirely mouse. This
 * is the answer to that, and it is also the answer to "it looks different from
 * other software" in the place where familiarity actually matters: how you
 * drive it, not how it looks.
 *
 * Ctrl+K opens it. That is the key every editor and half the web already use,
 * and borrowing it costs nothing and saves teaching.
 *
 * The list is built by the caller and passed in, because what is reachable
 * depends on where you are: Scribe can offer "compile" and "save as", the
 * shell can only offer the screens. A palette that offers actions which do
 * nothing where you stand is worse than a smaller palette.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { CornerDownLeft, Search } from 'lucide-react';

/**
 * Rank by where the match falls, not merely whether it matched.
 *
 * A query is far more often the start of a word than a fragment inside one, so
 * "com" should put "Compile" above "Uncomment" without either being excluded.
 */
function score(text, query) {
  const t = text.toLowerCase();
  const q = query.toLowerCase();
  if (!q) return 0;
  const at = t.indexOf(q);
  if (at === -1) return -1;
  if (at === 0) return 0;                                  // starts with it
  if (/[\s\-_/]/.test(t[at - 1] || '')) return 1;          // starts a word
  return 2;                                                // inside a word
}

export default function CommandPalette({ commands, onClose }) {
  const [query, setQuery] = useState('');
  const [cursor, setCursor] = useState(0);
  const listRef = useRef(null);

  const shown = useMemo(() => {
    const scored = commands
      .map((c) => ({ c, s: score(`${c.label} ${c.group || ''}`, query) }))
      .filter((x) => x.s >= 0);
    scored.sort((a, b) => a.s - b.s);
    return scored.map((x) => x.c).slice(0, 40);
  }, [commands, query]);

  useEffect(() => { setCursor(0); }, [query]);

  useEffect(() => {
    const el = listRef.current?.children?.[cursor];
    if (el?.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
  }, [cursor]);

  const run = (cmd) => {
    if (!cmd) return;
    onClose();          // close FIRST: an action may open a dialog of its own
    cmd.run();
  };

  const onKey = (e) => {
    if (e.key === 'Escape') { e.preventDefault(); return onClose(); }
    if (e.key === 'ArrowDown') { e.preventDefault(); return setCursor((c) => Math.min(c + 1, shown.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); return setCursor((c) => Math.max(c - 1, 0)); }
    if (e.key === 'Enter') { e.preventDefault(); return run(shown[cursor]); }
    return undefined;
  };

  return (
    <div className="cp-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="cp" role="dialog" aria-label="Commands">
        <div className="cp-input">
          <Search size={13} />
          <input
            autoFocus
            value={query}
            placeholder="Type a command or a paper"
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKey}
          />
        </div>

        <div className="cp-list" ref={listRef}>
          {shown.map((c, i) => (
            <button
              type="button"
              key={c.id}
              className={`cp-row ${i === cursor ? 'is-cursor' : ''}`}
              onMouseEnter={() => setCursor(i)}
              onClick={() => run(c)}
            >
              {c.icon}
              <span className="cp-label">{c.label}</span>
              {c.group && <span className="cp-group">{c.group}</span>}
              {c.hint && <kbd className="cp-hint">{c.hint}</kbd>}
            </button>
          ))}
          {!shown.length && <p className="cp-empty">Nothing matches “{query}”.</p>}
        </div>

        <div className="cp-foot">
          <CornerDownLeft size={10} /> run · ↑↓ move · Esc close
        </div>
      </div>
    </div>
  );
}
