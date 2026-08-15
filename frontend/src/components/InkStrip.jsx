import { useEffect, useRef, useState } from 'react';
import {
  PIGMENTS, PIGMENT_EARNED, EARNED_FOR, MODES,
  earned, mode, setMode,
} from '../utils/pigments';

/**
 * The press mark at the edge of the sheet, and the one place the app admits
 * how its colour works.
 *
 * A press sheet carries a strip of ink squares at its edge so the operator can
 * see each pigment is running. This one starts grey and takes its colours as
 * they are earned -- and because that is a mechanic and not a decoration, the
 * strip is also the control for it. It was previously a `div` marked
 * aria-hidden, which meant the app's signature idea was invisible to assistive
 * technology and undiscoverable to everyone else except as a tooltip.
 *
 * THE CEREMONY. Principle 6 says nothing moves that is not moving. An earning
 * is a real state change, so it gets the app's one piece of ceremony: the well
 * fills, and a line in the margin names what bought it. Once per pigment, four
 * times in the life of an install. utils/pigments.js fires the event; this
 * listens. Nothing else in the app animates on state.
 *
 * The wells still paint straight from their pigment tokens, so a pigment
 * arriving is a CSS change and the markup below never re-renders for it. The
 * only React state here belongs to the popover and the note.
 */

const MODE_COPY = {
  earn: {
    label: 'Earn it',
    hint: 'Start grey. Each colour arrives when you do the thing that earns it.',
  },
  full: {
    label: 'All four now',
    hint: 'Ink the full set today. What you go on to earn is still recorded.',
  },
  grey: {
    label: 'Stay grey',
    hint: 'Never paint. The notebook keeps earning quietly underneath.',
  },
};

/** How long the margin note holds before it fades. */
const NOTE_MS = 4600;

export default function InkStrip() {
  const [open, setOpen] = useState(false);
  // The pigment currently being announced, or null. Drives both the note and
  // the one-off fill on its well.
  const [note, setNote] = useState(null);
  // Read once per open rather than subscribed: nothing else in the app mutates
  // these, and the popover is the only reader.
  const [current, setCurrent] = useState(() => mode());
  const [have, setHave] = useState(() => earned());
  const btnRef = useRef(null);
  const timer = useRef(null);

  useEffect(() => {
    const onEarned = (e) => {
      const pigment = e.detail;
      if (!PIGMENTS.includes(pigment)) return;
      setHave(earned());
      setNote(pigment);
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setNote(null), NOTE_MS);
    };
    window.addEventListener(PIGMENT_EARNED, onEarned);
    return () => {
      window.removeEventListener(PIGMENT_EARNED, onEarned);
      clearTimeout(timer.current);
    };
  }, []);

  // Escape closes, and focus goes back to the thing that opened it.
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') { setOpen(false); btnRef.current?.focus(); }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  const choose = (next) => {
    setCurrent(setMode(next));
    setHave(earned());
  };

  const toggle = () => {
    if (!open) { setCurrent(mode()); setHave(earned()); }
    setOpen((o) => !o);
  };

  // The nudge: shown only while there is nothing to look at yet and the reader
  // has not been here. No storage key -- earning the first pigment retires it.
  const showHint = have.length === 0 && !open && current === 'earn';

  return (
    <div className="ink-mount">
      {note && (
        <p className="ink-note" role="status">
          <span className="ink-note-name">{note}</span>
          <span className="ink-note-for">{EARNED_FOR[note]}</span>
        </p>
      )}

      <button
        ref={btnRef}
        type="button"
        className="ink-strip"
        onClick={toggle}
        aria-expanded={open}
        aria-label={`Colour: ${MODE_COPY[current].label.toLowerCase()}. ${have.length} of 4 pigments earned. Change how colour arrives.`}
      >
        {PIGMENTS.map((p) => (
          <span
            key={p}
            className={`ink-well ink-${p}${note === p ? ' is-inking' : ''}`}
          />
        ))}
        {showHint && <span className="ink-hint">Choose</span>}
      </button>

      {open && (
        <>
          {/* Closes on any outside press. Not a scrim -- nothing is blocked. */}
          <div className="ink-catch" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="ink-pop" role="dialog" aria-label="How colour arrives">
            <p className="ink-pop-lede">
              ThinkStack ships grey and takes its colour from what you do with it.
            </p>

            <div className="ink-modes">
              {MODES.map((m) => (
                <label key={m} className={`ink-mode${current === m ? ' is-on' : ''}`}>
                  <input
                    type="radio"
                    name="pigment-mode"
                    checked={current === m}
                    onChange={() => choose(m)}
                  />
                  <span className="ink-mode-label">{MODE_COPY[m].label}</span>
                  <span className="ink-mode-hint">{MODE_COPY[m].hint}</span>
                </label>
              ))}
            </div>

            <ul className="ink-ledger">
              {PIGMENTS.map((p) => (
                <li key={p} className={have.includes(p) ? 'is-earned' : ''}>
                  <span className={`ink-well ink-${p}`} aria-hidden="true" />
                  <span className="ink-ledger-name">{p}</span>
                  <span className="ink-ledger-for">{EARNED_FOR[p]}</span>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  );
}
