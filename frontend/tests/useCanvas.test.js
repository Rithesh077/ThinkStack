import { describe, it, expect } from 'vitest';
import {
  makeAlpha, lassoFar, gestureFor, citedBy, edgeLit, hitRadius,
} from '../src/components/litgraph/useCanvas';

const m = (...ids) => new Map(ids.map((id) => [id, { score: 1 }]));

describe('makeAlpha', () => {
  it('dims everything that did not match, once a search is running', () => {
    const alpha = makeAlpha(m('a'), null, new Set());
    expect(alpha('a')).toBe(1);
    expect(alpha('b')).toBe(0.15);
  });

  it('leaves the scene alone when nothing is selected', () => {
    const alpha = makeAlpha(new Map(), null, new Set());
    expect(alpha('a')).toBe(1);
  });

  it('ranks focus above its neighbours above everything else', () => {
    const alpha = makeAlpha(new Map(), 'a', new Set(['b']));
    expect(alpha('a')).toBe(1);
    expect(alpha('b')).toBe(0.6);
    expect(alpha('c')).toBe(0.32);
  });

  // A search and a focus can be active at once; the search has to win, or a
  // node that did not match reads as merely "not adjacent" rather than "not a
  // result".
  it('lets a running search override the focus rules', () => {
    const alpha = makeAlpha(m('a'), 'b', new Set(['c']));
    expect(alpha('c')).toBe(0.15);
  });
});

describe('lassoFar', () => {
  const at = (x, y) => ({ x, y });

  it('drops points inside the threshold and keeps the ones outside', () => {
    expect(lassoFar(at(0, 0), at(3, 0), 1)).toBe(false);
    expect(lassoFar(at(0, 0), at(5, 0), 1)).toBe(true);
  });

  it('measures in screen pixels, not world units', () => {
    // Zoomed 4x in, 4 world units is 16 screen pixels: keep it.
    expect(lassoFar(at(0, 0), at(4, 0), 4)).toBe(true);
    // Zoomed out to a quarter, the same 4 units is 1 screen pixel: drop it.
    expect(lassoFar(at(0, 0), at(4, 0), 0.25)).toBe(false);
  });

  it('measures diagonally, not per axis', () => {
    expect(lassoFar(at(0, 0), at(3, 3), 1)).toBe(true);
  });
});

describe('gestureFor', () => {
  const empty = { closest: () => null };
  const node = { closest: (sel) => (sel === '.lg-node' ? {} : null) };
  const press = (shiftKey = false, target = empty, button = 0) => ({ target, button, shiftKey });

  // Plain drag pans. It selected for one release and made trackpads unusable:
  // every two-finger navigation gesture became a lasso.
  it('pans on a plain drag', () => {
    expect(gestureFor(press())).toBe('pan');
  });

  it('lassos only behind shift', () => {
    expect(gestureFor(press(true))).toBe('lasso');
  });

  // A press on a node must reach the node's own click listener untouched --
  // starting a gesture there flashes a lasso path that is then thrown away.
  it('leaves a press on a node alone, shift or not', () => {
    expect(gestureFor(press(false, node))).toBe('node');
    expect(gestureFor(press(true, node))).toBe('node');
  });

  it('ignores the right button, which belongs to the context menu', () => {
    expect(gestureFor(press(false, empty, 2))).toBe('none');
  });
});

/**
 * A gap is a node on the map that no edge touches: edges join papers, and a gap
 * is a claim about several of them. So focusing one used to dim the entire map
 * -- the papers it cites scored no better than papers it says nothing about,
 * and not one edge lit. The relation the marker exists to show was the one
 * thing selecting it hid.
 */
describe('citedBy', () => {
  const model = {
    gaps: [
      { gap_id: 'g1', doc_ids: ['a', 'b'] },
      { gap_id: 'g2', doc_ids: ['c'] },
    ],
  };

  it('gives the papers a gap cites', () => {
    expect([...citedBy(model, 'g1')]).toEqual(['a', 'b']);
  });

  it('gives nothing for a paper, which has edges of its own instead', () => {
    expect(citedBy(model, 'a')).toBe(null);
  });

  it('gives nothing when nothing is selected', () => {
    expect(citedBy(model, null)).toBe(null);
    expect(citedBy({}, 'g1')).toBe(null);
  });
});

describe('edgeLit', () => {
  const edge = (a, b) => ({ a, b });

  it('lights an edge touching the focused paper', () => {
    expect(edgeLit(edge('a', 'b'), 'a', null)).toBe(true);
    expect(edgeLit(edge('b', 'c'), 'a', null)).toBe(false);
  });

  // The point of selecting a gap: see how the papers it rests on relate.
  it('lights the edges between the papers a focused gap cites', () => {
    const cited = new Set(['a', 'b']);
    expect(edgeLit(edge('a', 'b'), 'g1', cited)).toBe(true);
  });

  it('leaves an edge with only one end in the gap alone', () => {
    const cited = new Set(['a', 'b']);
    expect(edgeLit(edge('b', 'z'), 'g1', cited)).toBe(false);
  });
});

// ─────────────────────────── D-18: hitting a node ───────────────────────────
//
// Two testers, on different operating systems, said the same thing without
// prompting: selecting a node needs more precision than it should. They are
// describing the geometry. A paper is drawn as a point of light with a radius
// of 4.5 to 8.5 units on a 1100x760 canvas, and the click listener sits on the
// group, so the target IS the dot. Zoomed out to 0.79x that is a four-pixel
// disc.
//
// The drawing is deliberate and stays: bubbles turned the plate into a bubble
// chart. What changes is that the TARGET stops being the drawing.

describe('hitRadius', () => {
  it('gives the smallest node a target far bigger than its dot', () => {
    expect(hitRadius(4.5)).toBeGreaterThanOrEqual(14);
  });

  it('never returns less than the dot it covers', () => {
    for (const r of [4.5, 6, 8.5, 20]) {
      expect(hitRadius(r)).toBeGreaterThanOrEqual(r);
    }
  });

  it('grows with the node, so a big node is not harder to hit than a small one', () => {
    expect(hitRadius(8.5)).toBeGreaterThan(hitRadius(4.5));
  });

  it('stays clear of the next node along', () => {
    // graph_builder.MIN_SEP is 0.055 of a 1100-unit canvas, so the closest two
    // nodes sit about 60 units apart. Two touching targets would make the
    // denser clusters ambiguous, which is a worse bug than a small target.
    expect(hitRadius(8.5) * 2).toBeLessThan(60);
  });
});
