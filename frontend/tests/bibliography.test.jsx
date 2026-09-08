/**
 * What the document cites, and whether each citation will resolve.
 *
 * The interesting states are the unhappy ones: a key cited but not defined
 * renders as [?] in the PDF, and an entry nothing cites is carried forever.
 * Both were invisible before this panel -- you had to open the .bib or compile.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act } from 'react';
import { createRoot } from 'react-dom/client';

const payload = {
  entries: [
    { key: 'vaswani2017attention', count: 3, in_bib: true, status: 'ok',
      doc_id: 'd1', title: 'Attention Is All You Need', year: '2017' },
    { key: 'ghost2024missing', count: 1, in_bib: false, status: 'missing',
      doc_id: null, title: null, year: null },
  ],
  unused: ['adams2007bayesian'],
  total_cited: 4,
};

vi.mock('../src/utils/api', () => ({
  projectFilesApi: { bibliography: vi.fn(async () => payload) },
}));

const { default: BibliographyPanel } = await import('../src/components/BibliographyPanel');

let host, opened;
const mount = async () => {
  opened = null;
  host = document.createElement('div');
  document.body.appendChild(host);
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  await act(async () => {
    createRoot(host).render(
      <BibliographyPanel projectId="p1" source="" onOpenPaper={(d) => { opened = d; }} />,
    );
  });
};
const expand = async () => {
  await act(async () => { host.querySelector('.bib-head').click(); });
};

beforeEach(() => { document.body.innerHTML = ''; });

describe('the bibliography panel', () => {
  it('starts collapsed, so the editor keeps its height', async () => {
    await mount();
    expect(host.querySelector('.bib-body')).toBeNull();
  });

  it('summarises without being opened', async () => {
    await mount();
    expect(host.textContent).toContain('2 cited');
    expect(host.textContent).toContain('1 missing');
    expect(host.textContent).toContain('1 unused');
  });

  it('says "missing" in words, not only in colour', async () => {
    await mount();
    // someone who cannot separate the tones still learns something is wrong
    expect(host.textContent).toContain('missing');
  });

  it('lists what is cited once opened', async () => {
    await mount();
    await expand();
    expect(host.textContent).toContain('vaswani2017attention');
    expect(host.textContent).toContain('Attention Is All You Need');
  });

  it('marks a key that is cited but not defined', async () => {
    await mount();
    await expand();
    const row = [...host.querySelectorAll('.bib-row')]
      .find((r) => r.textContent.includes('ghost2024missing'));
    expect(row.className).toContain('is-missing');
    expect(row.textContent).toContain('not in your library');
  });

  it('shows how many times something is cited', async () => {
    await mount();
    await expand();
    expect(host.textContent).toContain('×3');
  });

  it('names entries that are defined but never cited', async () => {
    await mount();
    await expand();
    expect(host.textContent).toContain('never cited');
    expect(host.textContent).toContain('adams2007bayesian');
  });

  it('clicks through to the paper in Library', async () => {
    await mount();
    await expand();
    const row = [...host.querySelectorAll('.bib-row')]
      .find((r) => r.textContent.includes('vaswani'));
    await act(async () => { row.querySelector('button').click(); });
    expect(opened).toBe('d1');
  });

  it('offers no link for a key that is not in the library', async () => {
    await mount();
    await expand();
    const row = [...host.querySelectorAll('.bib-row')]
      .find((r) => r.textContent.includes('ghost2024missing'));
    expect(row.querySelector('button')).toBeNull();
  });
});
