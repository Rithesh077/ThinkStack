/**
 * The cite trigger, driven the way a person drives it: type into a textarea
 * and see whether the list opens.
 *
 * A unit test on the regex would have passed while the feature did not. What
 * decides whether this works is the round trip -- keystroke, state, caret
 * offset, the word that gets replaced -- so the test types.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { useState, useRef } from 'react';

const citations = [
  { doc_id: 'a1', key: 'vaswani2017attention', title: 'Attention Is All You Need',
    authors: ['Ashish Vaswani'], year: '2017', cited: false },
  { doc_id: 'b2', key: 'adams2007bayesian', title: 'Bayesian Online Changepoint Detection',
    authors: ['Ryan Prescott Adams'], year: '2007', cited: false },
];

vi.mock('../src/utils/api', () => ({
  papersApi: {
    citations: vi.fn(async () => ({ citations })),
    cite: vi.fn(async (_p, docId) => {
      const row = citations.find((c) => c.doc_id === docId);
      return { key: row.key, added: true, cite: `\\cite{${row.key}}` };
    }),
  },
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const { default: useCitePicker } = await import('../src/utils/useCitePicker');

// React installs its own `value` setter on the element and uses it to tell a
// real edit from a programmatic one. Assigning `el.value` directly bypasses
// that, so the change event arrives with React still holding the old value.
const nativeValue = Object.getOwnPropertyDescriptor(
  window.HTMLTextAreaElement.prototype, 'value',
).set;

/** A harness with the one thing the hook reads: a real textarea. */
function Harness({ initial = '', onPicker }) {
  const ref = useRef(null);
  const [source, setSource] = useState(initial);
  const picker = useCitePicker({
    textareaRef: ref,
    source,
    projectId: 'p1',
    applyEdit: (from, to, text) =>
      setSource((prev) => prev.slice(0, from) + text + prev.slice(to)),
  });
  onPicker({ ...picker, source });
  return (
    <textarea
      ref={ref}
      value={source}
      onChange={(e) => setSource(e.target.value)}
      onKeyDown={(e) => picker.onKeyDown(e)}
    />
  );
}

async function mount(initial = '') {
  const host = document.createElement('div');
  document.body.appendChild(host);
  const root = createRoot(host);
  let latest = null;
  await act(async () => {
    root.render(<Harness initial={initial} onPicker={(p) => { latest = p; }} />);
  });
  const el = host.querySelector('textarea');

  /** Type at the end, the way a keypress reaches a controlled textarea. */
  const type = async (text) => {
    await act(async () => {
      nativeValue.call(el, el.value + text);
      el.selectionStart = el.selectionEnd = el.value.length;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    // the caret read happens in an effect, which needs a settled render
    await act(async () => {});
  };

  const press = async (key) => {
    await act(async () => {
      el.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
    });
    await act(async () => {});
  };

  return { el, type, press, get: () => latest };
}

beforeEach(() => { document.body.innerHTML = ''; });

describe('the cite trigger', () => {
  it('opens the list when the word is typed', async () => {
    const h = await mount();
    await h.type('cite');
    expect(h.get().picker).not.toBeNull();
    expect(h.get().picker.rows).toHaveLength(2);
  });

  it('opens mid-sentence, after a space', async () => {
    const h = await mount('As shown in ');
    await h.type('cite');
    expect(h.get().picker).not.toBeNull();
  });

  it('filters as the author keeps typing', async () => {
    const h = await mount();
    await h.type('cite');
    await h.type(' bayes');
    expect(h.get().picker.rows.map((r) => r.key)).toEqual(['adams2007bayesian']);
  });

  it('matches on the author name too', async () => {
    const h = await mount();
    await h.type('cite vaswani');
    expect(h.get().picker.rows.map((r) => r.key)).toEqual(['vaswani2017attention']);
  });

  it('closes when nothing matches, so prose does not drag a list along', async () => {
    const h = await mount();
    await h.type('cite the usual sources here');
    expect(h.get().picker).toBeNull();
  });

  it('does not fire mid-word', async () => {
    const h = await mount();
    await h.type('recite');
    expect(h.get().picker).toBeNull();
  });

  it('does not fire on a citation already written', async () => {
    const h = await mount();
    await h.type('\\cite');
    expect(h.get().picker).toBeNull();
  });

  it('replaces the word with the citation on Enter', async () => {
    const h = await mount('As shown in ');
    await h.type('cite bayes');
    await h.press('Enter');
    expect(h.get().source).toBe('As shown in \\cite{adams2007bayesian}');
  });

  it('moves the highlight with the arrow keys', async () => {
    const h = await mount();
    await h.type('cite');
    await h.press('ArrowDown');
    await h.press('Enter');
    expect(h.get().source).toBe('\\cite{adams2007bayesian}');
  });

  it('Escape leaves the word alone and stays closed', async () => {
    const h = await mount('we ');
    await h.type('cite');
    await h.press('Escape');
    expect(h.get().picker).toBeNull();
    await h.type(' b');
    expect(h.get().picker).toBeNull();
    expect(h.get().source).toBe('we cite b');
  });
});
