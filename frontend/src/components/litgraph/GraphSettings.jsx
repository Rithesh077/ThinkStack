import { useState } from 'react';

/**
 * The cog panel.
 *
 * Obsidian puts four groups behind the graph's cog -- Filters, Groups, Display
 * and Forces -- and that grouping is worth borrowing whole, because anyone who
 * has used it already knows where to look. Three of the four are here. Groups
 * is not, and deliberately: a Group in Obsidian is a saved search painted in a
 * colour, and this map has neither spare colour (hue says what you are doing,
 * never what something is) nor the need (themes already cluster the library by
 * meaning, computed rather than typed).
 *
 * Nothing in here holds graph state. Every control writes straight through to
 * the canvas handle, which owns the scene; the only local state is which
 * sections are open, which is a property of this panel and nobody else's
 * business.
 */
export default function GraphSettings({ canvas, blend, onBlend, pinCount, onUnpinAll, onClose }) {
  const [open, setOpen] = useState({ filters: true, display: true, forces: true });
  // Sliders write through on every input event and the canvas is imperative,
  // so React never re-renders from them -- this mirror is only so the readouts
  // and thumbs move while you drag.
  const [v, setV] = useState({ ...canvas.display, ...canvas.forces });

  const toggle = (k) => setOpen((o) => ({ ...o, [k]: !o[k] }));
  const caret = (k) => (open[k] ? '−' : '+');

  const slide = (group, name, value) => {
    setV((p) => ({ ...p, [name]: value }));
    if (group === 'display') canvas.setDisplay(name, value);
    else canvas.setForce(name, value);
  };

  // At the Meaning end there is no simulation running, so there is nothing for
  // the three force sliders to act on.
  const still = blend <= 0;

  return (
    <div className="lg-settings" role="group" aria-label="Graph settings">
      <div className="lg-settings-head">
        Graph settings
        <button className="lg-x" onClick={onClose} aria-label="Close graph settings">✕</button>
      </div>

      <Group id="filters" label="Filters" open={open} caret={caret} toggle={toggle}>
        {/* Themes and Gaps keep their chips in the top bar. Repeating them
            here would be two controls for one boolean, and two controls for one
            boolean drift. */}
        <div className="lg-fil">
          <Chip label="Orphans" on={canvas.filters.orphans}
            onChange={(on) => canvas.setFilter('orphans', on)} />
          <Chip label="Unanalysed" on={canvas.filters.unanalysed}
            onChange={(on) => canvas.setFilter('unanalysed', on)} />
          <Chip label="Encrypted" on={canvas.filters.encrypted}
            onChange={(on) => canvas.setFilter('encrypted', on)} />
        </div>
        <p className="lg-settings-note">
          An orphan is a paper with no similarity above 0.35: on the plate, but
          arguing with nothing.
        </p>
      </Group>

      <Group id="display" label="Display" open={open} caret={caret} toggle={toggle}>
        <span className="lg-settings-lbl">Node size</span>
        <div className="lg-seg">
          {[['length', 'Length'], ['links', 'Links'], ['uniform', 'Uniform']].map(([k, label]) => (
            <button
              key={k}
              className={canvas.display.size === k ? 'on' : ''}
              onClick={() => { canvas.setDisplay('size', k); setV((p) => ({ ...p, size: k })); }}
            >
              {label}
            </button>
          ))}
        </div>
        <Slider label="Label fade" name="fade" value={v.fade} min={0} max={1} step={0.01}
          read={v.fade.toFixed(2)} onChange={(n) => slide('display', 'fade', n)} />
        <Slider label="Link thickness" name="thickness" value={v.thickness} min={0} max={1} step={0.01}
          read={v.thickness.toFixed(2)} onChange={(n) => slide('display', 'thickness', n)} />
        <p className="lg-settings-note">
          Zooming out drops to territories on its own; the fade decides how
          early the titles you are left with come in.
        </p>
      </Group>

      <Group id="forces" label="Forces" open={open} caret={caret} toggle={toggle}>
        {still && (
          <p className="lg-settings-note">
            The map is the projection, so nothing is moving. Slide the dial in
            the top bar away from Meaning to relax it.
          </p>
        )}
        <Slider label="Repel force" name="repel" value={v.repel} min={0} max={1} step={0.01}
          read={v.repel.toFixed(2)} off={still} onChange={(n) => slide('forces', 'repel', n)} />
        <Slider label="Link force" name="link" value={v.link} min={0} max={1} step={0.01}
          read={v.link.toFixed(2)} off={still} onChange={(n) => slide('forces', 'link', n)} />
        <Slider label="Link distance" name="distance" value={v.distance} min={20} max={200} step={1}
          read={String(Math.round(v.distance))} off={still}
          onChange={(n) => slide('forces', 'distance', n)} />
        {!still && (
          <button className="btn btn-secondary btn-sm lg-settings-wide" onClick={() => onBlend(0)}>
            Back to the projection
          </button>
        )}
        {/* Only when there is something to undo -- a control for a state you
            are not in is a control you have to read and dismiss. */}
        {pinCount > 0 && (
          <>
            <p className="lg-settings-note">
              {pinCount} paper{pinCount === 1 ? '' : 's'} placed by hand, ringed
              on the plate. Double-click one to let it go.
            </p>
            <button className="btn btn-secondary btn-sm lg-settings-wide" onClick={onUnpinAll}>
              Unpin all · {pinCount}
            </button>
          </>
        )}
      </Group>
    </div>
  );
}

function Group({ id, label, open, caret, toggle, children }) {
  return (
    <div className="lg-settings-grp">
      <button className="lg-settings-grp-head" onClick={() => toggle(id)} aria-expanded={open[id]}>
        {label}
        <span aria-hidden="true">{caret(id)}</span>
      </button>
      {open[id] && <div className="lg-settings-body">{children}</div>}
    </div>
  );
}

/**
 * Uncontrolled on purpose: the canvas is the source of truth for a layer, and
 * a chip that owned its own boolean would drift from it. Same trick the two
 * layer chips in the top bar already use.
 */
function Chip({ label, on = true, amber = false, onChange }) {
  const [live, setLive] = useState(on);
  return (
    <button
      className={`lg-chip${live ? ' on' : ''}${amber ? ' lg-amber' : ''}`}
      aria-pressed={live}
      onClick={() => { setLive(!live); onChange(!live); }}
    >
      {label}
    </button>
  );
}

/** A ruled line with a square of ink on it. See .lg-slider in litgraph.css. */
function Slider({ label, name, value, min, max, step, read, off = false, onChange }) {
  return (
    <div className={`lg-slider${off ? ' is-off' : ''}`}>
      <div className="lg-slider-top">
        <label htmlFor={`lg-f-${name}`}>{label}</label>
        <var>{read}</var>
      </div>
      <input
        id={`lg-f-${name}`}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={off}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </div>
  );
}
