/**
 * The cite list. Detection, filtering and keyboard live in `useCitePicker`;
 * this only draws what that decided, positioned absolutely inside `.pw-editor`.
 */

/** The list itself. Positioned by the hook, absolute inside `.pw-editor`. */
export function CitePicker({ picker }) {
  if (!picker) return null;
  const { rows, active, busy, top, bottom, left, onPick, onHover } = picker;

  return (
    <div
      className="pw-cite"
      // `top` and `bottom` are exclusive: the hook returns whichever side of
      // the caret has room, and null for the other.
      style={top === null ? { bottom, left } : { top, left }}
      role="listbox"
    >
      {rows.length === 0 ? (
        <div className="pw-cite-empty">
          Nothing in the library yet. Add papers and they will be citable here.
        </div>
      ) : rows.map((row, i) => (
        <button
          type="button"
          key={row.doc_id}
          className={`pw-cite-row${i === active ? ' is-active' : ''}`}
          role="option"
          aria-selected={i === active}
          disabled={busy}
          onMouseEnter={() => onHover(i)}
          // mousedown, not click: click fires after the textarea has already
          // lost focus, and by then the caret offset the insert needs is gone.
          onMouseDown={(e) => { e.preventDefault(); onPick(row); }}
        >
          <span className="pw-cite-title">{row.title}</span>
          <span className="pw-cite-meta">
            {(row.authors || []).slice(0, 2).join(', ')}
            {(row.authors || []).length > 2 ? ' et al.' : ''}
            {row.year ? ` · ${row.year}` : ''}
            {/* Said in a word rather than marked with a dot: the author is
                deciding whether they have used this paper before, and a
                floating middot does not answer that. */}
            {row.cited ? ' · cited' : ''}
          </span>
          <span className="pw-cite-key">{row.key}</span>
        </button>
      ))}
    </div>
  );
}
