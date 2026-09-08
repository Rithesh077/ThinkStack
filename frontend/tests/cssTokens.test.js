/**
 * Stylesheet invariants that jsdom cannot check, because jsdom computes no
 * cascade and no layout. Both of these shipped as bugs first.
 *
 * This exists because of a bug no other test in this repo could see. The
 * template menu was written with `background: var(--surface-1)`. There is no
 * `--surface-1` in this project -- the token is `--surface` -- so the
 * declaration was invalid, the background resolved to nothing, and the menu
 * rendered transparent on top of the file list. Everything passed: the CSS is
 * syntactically valid, the build succeeds, and jsdom computes no layout or
 * cascade, so no interface test notices a panel you can see through.
 *
 * A missing token always fails this way -- silently, and only on screen. The
 * check is a string comparison over two files, so it costs nothing to keep.
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..', 'src');

/** Comments are not code: a token NAMED in a comment is not a token USED. */
const strip = (css) => css.replace(/\/\*[\s\S]*?\*\//g, '');

function stylesheets(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) out.push(...stylesheets(p));
    else if (e.name.endsWith('.css')) out.push(p);
  }
  return out;
}

const files = stylesheets(SRC);
const sheets = files.map((f) => ({ name: f.split('/').pop(), css: strip(readFileSync(f, 'utf8')) }));

const defined = new Set();
for (const { css } of sheets) {
  for (const m of css.matchAll(/^\s*(--[\w-]+)\s*:/gm)) defined.add(m[1]);
}

describe('css custom properties', () => {
  it('finds the stylesheets at all', () => {
    // A test that silently scans nothing passes forever.
    expect(files.length).toBeGreaterThan(0);
    expect(defined.size).toBeGreaterThan(20);
  });

  it('every token read is a token defined', () => {
    const missing = [];
    for (const { name, css } of sheets) {
      // `var(--x, fallback)` is deliberate and survives an undefined token,
      // so only unguarded reads are failures.
      for (const m of css.matchAll(/var\(\s*(--[\w-]+)\s*(,)?/g)) {
        if (!m[2] && !defined.has(m[1])) missing.push(`${name}: ${m[1]}`);
      }
    }
    expect(
      [...new Set(missing)],
      'undefined custom properties resolve to nothing and fail only on screen',
    ).toEqual([]);
  });
});


/**
 * A flex row distributes free space EQUALLY between every `margin-left: auto`
 * in it. One auto margin means "push this and everything after it to the
 * right", which is almost always what was meant. Two means each item lands at
 * a position that depends on how wide its siblings happen to be.
 *
 * This shipped: `.ft-when` (the date) and `.ft-dot` (the compiled mark) both
 * declared it, so the dates in the Scribe tree sat at a different x in every
 * row -- further left the longer the paper's name, and hard right on any row
 * with no dot. It reads as scattered, and no test could see it.
 */
describe('the Scribe tree row', () => {
  const sheet = sheets.find((s) => s.name === 'index.css').css;

  /** The declarations inside one selector's block. */
  const block = (selector) => {
    const i = sheet.indexOf(`${selector} {`);
    if (i === -1) throw new Error(`no rule for ${selector}`);
    return sheet.slice(i, sheet.indexOf('}', i));
  };

  // Grouped by the row each class actually appears in. A project row carries
  // the date and the compiled mark; a file row carries a size. They never
  // co-occur, so each row type is checked on its own -- .ft-size having its
  // own auto margin is correct, because it is the only pusher in its row.
  const ROW_TYPES = {
    'a project row': ['.ft-when', '.ft-dot'],
    'a file row': ['.ft-size'],
  };

  it.each(Object.entries(ROW_TYPES))(
    '%s has exactly one auto left margin',
    (_name, classes) => {
      const pushers = classes.filter((c) => /margin-left:\s*auto/.test(block(c)));
      expect(
        pushers,
        'two auto margins split the free space, so neither lands where it looks like it should',
      ).toHaveLength(1);
    },
  );

  it('gives the date the auto margin, so it and the dot travel together', () => {
    expect(block('.ft-when')).toMatch(/margin-left:\s*auto/);
    expect(block('.ft-dot')).not.toMatch(/margin-left:\s*auto/);
  });

  it('reserves a width for the date so the column does not ripple', () => {
    // "now" and "Aug 15" are different widths; without a reserved,
    // right-aligned box they end at different places.
    expect(block('.ft-when')).toMatch(/min-width/);
    expect(block('.ft-when')).toMatch(/text-align:\s*right/);
  });
});
