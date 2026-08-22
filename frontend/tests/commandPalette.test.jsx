/**
 * Ctrl+K, and what it can reach.
 *
 * The application had exactly one shortcut before this, so the core loop was
 * entirely mouse. The behaviour worth pinning is the ranking -- a query is far
 * more often the start of a word than a fragment inside one -- and that
 * running a command closes the palette before the action fires, since an
 * action may open a dialog of its own.
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';

const { default: CommandPalette } = await import('../src/components/CommandPalette');

const ran = [];
const commands = [
  { id: 'a', label: 'Go to Library', group: 'Screen', run: () => ran.push('library') },
  { id: 'b', label: 'Go to Scribe', group: 'Screen', run: () => ran.push('scribe') },
  { id: 'c', label: 'Uncomment selection', group: 'Edit', run: () => ran.push('uncomment') },
  { id: 'd', label: 'Compile', group: 'Paper', run: () => ran.push('compile') },
];

let host, closed;
const mount = async () => {
  ran.length = 0; closed = false;
  host = document.createElement('div');
  document.body.appendChild(host);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  await act(async () => {
    createRoot(host).render(
      <CommandPalette commands={commands} onClose={() => { closed = true; }} />,
    );
  });
};
const type = async (v) => {
  const input = host.querySelector('.cp-input input');
  await act(async () => {
    const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    set.call(input, v);
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
};
const rows = () => [...host.querySelectorAll('.cp-row')].map((r) => r.textContent);
const key = async (k) => {
  const input = host.querySelector('.cp-input input');
  await act(async () => {
    input.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }));
  });
};

beforeEach(() => { document.body.innerHTML = ''; });

describe('the command palette', () => {
  it('offers everything before you type', async () => {
    await mount();
    expect(rows()).toHaveLength(commands.length);
  });

  it('ranks a word start above a match inside a word', async () => {
    await mount();
    await type('com');
    // "Compile" starts with it; "Uncomment" only contains it
    expect(rows()[0]).toContain('Compile');
    expect(rows().join(' ')).toContain('Uncomment');   // still offered, not hidden
  });

  it('matches the group as well as the label', async () => {
    await mount();
    await type('screen');
    expect(rows()).toHaveLength(2);
  });

  it('runs the highlighted command on Enter', async () => {
    await mount();
    await type('scribe');
    await key('Enter');
    expect(ran).toEqual(['scribe']);
  });

  it('closes before the action fires', async () => {
    /* An action may open a dialog of its own; closing afterwards would tear
       down the thing it just opened. */
    await mount();
    const order = [];
    const one = [{ id: 'x', label: 'Opens something', run: () => order.push('ran') }];
    host = document.createElement('div');
    document.body.appendChild(host);
    await act(async () => {
      createRoot(host).render(
        <CommandPalette commands={one} onClose={() => order.push('closed')} />,
      );
    });
    await act(async () => { host.querySelector('.cp-row').click(); });
    expect(order).toEqual(['closed', 'ran']);
  });

  it('moves with the arrow keys', async () => {
    await mount();
    await key('ArrowDown');
    await key('Enter');
    expect(ran).toEqual(['scribe']);       // the second entry
  });

  it('escape closes without running anything', async () => {
    await mount();
    await key('Escape');
    expect(closed).toBe(true);
    expect(ran).toEqual([]);
  });

  it('says so when nothing matches', async () => {
    await mount();
    await type('zzzzz');
    expect(host.textContent).toContain('Nothing matches');
  });
});
