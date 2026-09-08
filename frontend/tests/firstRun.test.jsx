/**
 * What a brand-new install offers you.
 *
 * The Library is the first screen, and on a fresh machine it is empty. It used
 * to say only "drop a PDF here" -- which is a door with nothing behind it for
 * someone who came to write a letter. Scribe needs no library at all, so the
 * empty state has to say so.
 *
 * These assert on rendered markup rather than on props: the defect was that a
 * new user read one instruction and concluded the app was locked, and only the
 * markup can show whether the second instruction is actually there.
 */
import { describe, it, expect, vi } from 'vitest';
import { StrictMode } from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';

const TEMPLATES = [
  { id: 'paper', label: 'Research paper', description: 'abstract, methodology, results' },
  { id: 'letter', label: 'Letter', description: 'a single page, no sections' },
  { id: 'cv', label: 'CV', description: 'dated entries' },
];

vi.mock('../src/utils/api', () => ({
  registryApi: { get: vi.fn(async () => ({ models: [], routing: {}, tasks: [], discovered: [], catalog: [], download: { status: 'idle' }, upgrade: null })) },
  systemApi: { diagnose: vi.fn(async () => ({ machine: {}, engine: {}, limits: {}, advice: [] })), health: vi.fn(async () => ({})), jobs: vi.fn(async () => ({})) },
  modelsApi: {}, hfApi: {}, searchApi: {}, encryptionApi: {},
  // the empty library, which is the whole point
  documentsApi: { list: vi.fn(async () => ({ documents: [] })) },
  graphApi: { get: vi.fn(async () => ({ nodes: [], edges: [], themes: [], gaps: [] })) },
  analysisApi: { history: vi.fn(async () => ({ runs: [] })) },
  gapsApi: { history: vi.fn(async () => ({ runs: [] })) },
  papersApi: {
    list: vi.fn(async () => ({ projects: [] })),
    templates: vi.fn(async () => ({ templates: TEMPLATES, default: 'paper' })),
  },
  useJobs: () => ({ active: false, label: '', done: 0, total: 0, queued: 0, error: '' }),
  useLlmBusy: () => ({ busy: false, label: '' }),
  llmBusyStore: { subscribe: () => () => {}, getSnapshot: () => ({ count: 0, label: '' }) },
}));

async function render(path, Component) {
  const el = document.createElement('div');
  document.body.appendChild(el);
  const root = createRoot(el);
  await new Promise((resolve) => {
    root.render(
      <StrictMode><MemoryRouter initialEntries={[path]}><Component /></MemoryRouter></StrictMode>,
    );
    setTimeout(resolve, 80);
  });
  const html = el.innerHTML;
  root.unmount();
  el.remove();
  return html;
}

/** Render, click one thing, and return the markup that results. */
async function renderAndClick(path, Component, selector) {
  const el = document.createElement('div');
  document.body.appendChild(el);
  const root = createRoot(el);
  await new Promise((resolve) => {
    root.render(
      <StrictMode><MemoryRouter initialEntries={[path]}><Component /></MemoryRouter></StrictMode>,
    );
    setTimeout(resolve, 80);
  });
  const btn = el.querySelector(selector);
  if (!btn) throw new Error(`nothing matched ${selector}`);
  await act(async () => { btn.click(); });
  const html = el.innerHTML;
  root.unmount();
  el.remove();
  return { html };
}

describe('an empty library is not a locked one', () => {
  it('still tells you how to read a paper', async () => {
    const { default: Library } = await import('../src/components/Library');
    expect(await render('/', Library)).toContain('Nothing read yet');
  });

  it('offers writing as well as reading', async () => {
    const { default: Library } = await import('../src/components/Library');
    const html = await render('/', Library);
    expect(html).toMatch(/start writing/i);
  });

  it('the offer is a real link to Scribe, not just words', async () => {
    // A sentence mentioning Scribe with no way to reach it is the same dead
    // end in nicer prose.
    const { default: Library } = await import('../src/components/Library');
    expect(await render('/', Library)).toMatch(/href="\/write"/);
  });
});

describe('a new paper can be something other than a paper', () => {
  // The control that CHOOSES a template must never displace the control that
  // CREATES one. A <select> in this header was 120px of a 200px sidebar and
  // pushed the + button off the edge: templates became selectable and papers
  // became uncreatable. jsdom computes no layout, so it cannot catch the
  // clipping -- what it can check is that the + is still rendered, still
  // enabled, and still the thing that starts a paper.
  it('the new-paper button survives having templates', async () => {
    const { default: Scribe } = await import('../src/components/Scribe');
    const html = await render('/write', Scribe);
    expect(html).toMatch(/title="New paper[^"]*"/);
  });

  it('does not put a dropdown in the header', async () => {
    const { default: Scribe } = await import('../src/components/Scribe');
    const html = await render('/write', Scribe);
    expect(html).not.toMatch(/<select/);
  });

  it('offers every template once the menu is open', async () => {
    const { default: Scribe } = await import('../src/components/Scribe');
    const { html } = await renderAndClick('/write', Scribe, 'button[title^="New paper"]');
    for (const t of TEMPLATES) {
      expect(html, `${t.id} is missing from the menu`).toContain(t.label);
    }
  });

  it('says what each template is, not just its name', async () => {
    // The reason this is a menu and not a dropdown: "CV" alone does not tell
    // anyone what they are about to get.
    const { default: Scribe } = await import('../src/components/Scribe');
    const { html } = await renderAndClick('/write', Scribe, 'button[title^="New paper"]');
    for (const t of TEMPLATES) {
      expect(html, `${t.id} has no description`).toContain(t.description);
    }
  });

  it('labels every entry rather than rendering blanks', async () => {
    // Regression: the route sends `label` and the picker read `name`, so every
    // entry rendered empty. Only text content can catch this.
    const { default: Scribe } = await import('../src/components/Scribe');
    const { html } = await renderAndClick('/write', Scribe, 'button[title^="New paper"]');
    expect(html).not.toMatch(/class="ft-tpl-label"><\/span>/);
  });

  it('the menu is closed until asked for', async () => {
    const { default: Scribe } = await import('../src/components/Scribe');
    const html = await render('/write', Scribe);
    expect(html).not.toContain('ft-tpl-menu');
  });
});
