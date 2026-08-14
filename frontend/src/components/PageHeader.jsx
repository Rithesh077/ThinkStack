/**
 * The masthead of the page.
 *
 * The title used to carry an acid-green SVG "brush-slash" that drew itself on
 * mount. It is gone: the signature is the serif now, closed by the single heavy
 * rule under the header. A 42px Newsreader title does not need a glowing green
 * stroke underneath to read as a title, and the slash cost an SVG, a keyframe
 * animation and a drop-shadow filter on every page mount to say so.
 *
 * pass action buttons as children - they align to the title baseline on the
 * right, replacing the ad-hoc per-page header markup (and its alignment bugs).
 *
 * There is no subtitle. A sentence explaining the page is worth reading once
 * and was then occupying a strip of every screen forever -- which Scribe needs
 * for its editor and preview to have half the height each. That copy now lives
 * in features.js and is shown by the "i" in the bottom-left corner.
 *
 * `folio` is the count, set on the rule at the right-hand end: running head on
 * the left, folio on the right, which is how a printed page has stated where
 * you are for four hundred years. Library had this already as a separate
 * `.tally` strip below the header -- a second horizontal rule, 40px of height,
 * to say "3 papers" -- and Bench and Scribe had nothing. One slot, every page,
 * and the strip goes.
 *
 * Pass `<span className="tally-item"><b>3</b>papers</span>` per count; the
 * container supplies the mono and the colour. Deliberately JSX rather than a
 * data prop: every page counts something different, and a shape general enough
 * for all three would be longer than the markup it replaced.
 */
export default function PageHeader({ title, folio, className = '', children }) {
  // `title` is optional and the pages no longer pass one. The nav says which
  // screen you are on, the mark in the margin follows it, and Library now
  // introduces the others by name -- so a heading reading "Scribe" above the
  // Scribe screen only cost the editor a strip of height. The masthead stays
  // for what it actually carries: the folio and the page's own actions.
  if (!title && !folio && !children) return null;

  return (
    <div className={`page-header ${!title ? 'is-untitled' : ''} ${className}`.trim()}>
      {title && (
        <div className="page-header-left">
          <h2 className="ph-title">
            <span className="ph-title-text">{title}</span>
          </h2>
        </div>
      )}
      {folio && <div className="ph-folio">{folio}</div>}
      {children}
    </div>
  );
}
