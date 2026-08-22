/**
 * Choosing a file by navigating to it.
 *
 * The point of this component is that it replaces typing a path, so the tests
 * are about navigation and selection: can you get into a folder, back out of
 * it, and hand back a path -- and are you stopped from picking something the
 * backend would refuse anyway.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';

const tree = {
  '/home/u': {
    path: '/home/u', parent: '/home', home: '/home/u',
    entries: [
      { name: 'papers', path: '/home/u/papers', is_dir: true },
      { name: 'refs.bib', path: '/home/u/refs.bib', is_dir: false, size: 2048, linkable: true },
      { name: 'notes.docx', path: '/home/u/notes.docx', is_dir: false, size: 10, linkable: false },
    ],
  },
  '/home/u/papers': {
    path: '/home/u/papers', parent: '/home/u', home: '/home/u',
    entries: [
      { name: 'draft.tex', path: '/home/u/papers/draft.tex', is_dir: false, size: 99, linkable: true },
    ],
  },
};

vi.mock('../src/utils/api', () => ({
  projectFilesApi: {
    browse: vi.fn(async (p) => tree[p || '/home/u']),
  },
}));

const { default: PathPicker } = await import('../src/components/PathPicker');

let host, root, picked, cancelled;
const mount = async (mode = 'file') => {
  picked = null; cancelled = false;
  host = document.createElement('div');
  document.body.appendChild(host);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  await act(async () => {
    root = createRoot(host);
    root.render(<PathPicker mode={mode} onPick={(p) => { picked = p; }} onCancel={() => { cancelled = true; }} />);
  });
};
const rows = () => [...host.querySelectorAll('.pp-row')];
const rowNamed = (n) => rows().find((r) => r.textContent.includes(n));

beforeEach(() => { document.body.innerHTML = ''; });

describe('the path chooser', () => {
  it('opens in the home folder', async () => {
    await mount();
    expect(host.textContent).toContain('/home/u');
    expect(rowNamed('papers')).toBeTruthy();
    expect(rowNamed('refs.bib')).toBeTruthy();
  });

  it('navigates into a folder on click', async () => {
    await mount();
    await act(async () => { rowNamed('papers').click(); });
    expect(rowNamed('draft.tex')).toBeTruthy();
  });

  it('hands back the path of a file that is picked', async () => {
    await mount();
    await act(async () => { rowNamed('refs.bib').click(); });
    expect(picked).toBe('/home/u/refs.bib');
  });

  it('will not pick a file the backend would refuse', async () => {
    await mount();
    await act(async () => { rowNamed('notes.docx').click(); });
    // shown, so the folder does not look emptier than it is -- but not offered
    expect(picked).toBeNull();
    expect(rowNamed('notes.docx').className).toContain('is-off');
  });

  it('in folder mode it lists only folders and takes the current one', async () => {
    await mount('folder');
    expect(rowNamed('refs.bib')).toBeFalsy();
    expect(rowNamed('papers')).toBeTruthy();
    const take = [...host.querySelectorAll('button')].find((b) => b.textContent.includes('Use this folder'));
    await act(async () => { take.click(); });
    expect(picked).toBe('/home/u');
  });

  it('escape cancels without choosing anything', async () => {
    await mount();
    const input = host.querySelector('.pp-filter input');
    await act(async () => {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    });
    expect(cancelled).toBe(true);
    expect(picked).toBeNull();
  });

  it('typing narrows the list rather than being a path', async () => {
    await mount();
    const input = host.querySelector('.pp-filter input');
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(input, 'refs');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    expect(rowNamed('refs.bib')).toBeTruthy();
    expect(rowNamed('papers')).toBeFalsy();
  });
});
