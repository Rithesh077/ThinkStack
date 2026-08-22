/**
 * Linked files, driven the way a person meets them.
 *
 * The states worth testing are the unhappy ones. A link whose file has moved
 * or vanished is the whole reason this feature needs an interface at all --
 * a happy link is just a filename.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';

const links = {
  current: [
    { id: 'l1', name: 'refs.bib', path: '/home/u/refs.bib', size: 2048,
      status: 'ok', resolved: '/home/u/refs.bib' },
    { id: 'l2', name: 'moved.tex', path: '/home/u/moved.tex', size: 100,
      status: 'moved', resolved: '/home/u/chapters/moved.tex' },
    { id: 'l3', name: 'gone.png', path: '/home/u/gone.png', size: 50,
      status: 'missing', resolved: null },
  ],
};

const calls = { relink: [], unlink: [], copy: [], add: [] };

vi.mock('../src/utils/api', () => ({
  projectFilesApi: {
    links: vi.fn(async () => ({ links: links.current })),
    // the chooser reads directories through the backend, so repairing a link
    // now goes: click Locate -> a window opens -> click the file
    browse: vi.fn(async () => ({
      path: '/home/u', parent: '/home', home: '/home/u',
      entries: [
        { name: 'gone.png', path: '/home/u/found/gone.png', is_dir: false,
          size: 50, linkable: true },
      ],
    })),
    addLink: vi.fn(async (p, path) => { calls.add.push(path); return { links: links.current }; }),
    relink: vi.fn(async (p, id, path) => { calls.relink.push([id, path]); return { links: links.current }; }),
    unlink: vi.fn(async (p, id) => { calls.unlink.push(id); return { links: [] }; }),
    copyLinkIn: vi.fn(async (p, id) => { calls.copy.push(id); return { links: links.current, files: [] }; }),
  },
}));

const { default: LinkedFiles } = await import('../src/components/LinkedFiles');

let host, root;
beforeEach(async () => {
  calls.relink.length = 0; calls.unlink.length = 0;
  calls.copy.length = 0; calls.add.length = 0;
  host = document.createElement('div');
  document.body.appendChild(host);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  await act(async () => {
    root = createRoot(host);
    root.render(<LinkedFiles projectId="p1" />);
  });
});

const text = () => host.textContent;
const buttons = () => [...host.querySelectorAll('button')];

describe('linked files', () => {
  it('lists what the project references', () => {
    expect(text()).toContain('refs.bib');
    expect(text()).toContain('moved.tex');
    expect(text()).toContain('gone.png');
  });

  it('says "missing" in words, not only in colour', () => {
    // someone who cannot tell the tones apart still learns which file is broken
    expect(text()).toContain('missing');
  });

  it('says when a file was found somewhere new', () => {
    expect(text()).toContain('moved');
  });

  it('offers a way to find a missing file', () => {
    expect(buttons().some((b) => b.textContent.includes('Locate'))).toBe(true);
  });

  it('Locate opens a chooser rather than asking for a typed path', async () => {
    const locate = buttons().find((b) => b.textContent.includes('Locate'));
    await act(async () => { locate.click(); });
    // a window, with the folder listed in it -- not an input to remember a path
    expect(host.querySelector('.pp')).toBeTruthy();
    expect(host.textContent).toContain('gone.png');
  });

  it('repairing a link keeps the same link rather than adding one', async () => {
    const locate = buttons().find((b) => b.textContent.includes('Locate'));
    await act(async () => { locate.click(); });
    const row = [...host.querySelectorAll('.pp-row')].find((r) => r.textContent.includes('gone.png'));
    await act(async () => { row.click(); });
    expect(calls.relink).toEqual([['l3', '/home/u/found/gone.png']]);
    expect(calls.add).toHaveLength(0);          // not a second row
  });

  it('unlinking is offered, and is not a delete', async () => {
    // the title is the promise: the file itself is not ours
    const forget = buttons().find((b) => (b.title || '').includes('not deleted'));
    expect(forget).toBeTruthy();
    await act(async () => { forget.click(); });
    expect(calls.unlink).toHaveLength(1);
  });

  it('copying in is available for a file that is present', async () => {
    const copy = buttons().find((b) => (b.title || '').includes('Copy into'));
    expect(copy).toBeTruthy();
    await act(async () => { copy.click(); });
    expect(calls.copy).toHaveLength(1);
  });
});
