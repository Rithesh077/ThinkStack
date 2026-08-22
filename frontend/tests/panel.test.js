import { describe, it, expect } from 'vitest';
import {
  clampPanel, neighbours, nearestFurthest, gapPassages, localGraph,
} from '../src/components/litgraph/panel';

describe('clampPanel', () => {
  it('will not go narrower than the reader stays readable at', () => {
    expect(clampPanel(100, 1600)).toBe(280);
  });

  // The ceiling was half the window, because the map was the point of the page.
  // Then the panel grew a PDF reader, and reading wants width -- a hard stop at
  // 50% meant dragging further did nothing, which reads as a broken grip.
  it('lets the reader take most of the window', () => {
    expect(clampPanel(1400, 1600)).toBe(1240);   // 1600 - 360 of canvas
  });

  it('but never erases the map', () => {
    // whatever you drag, something recognisable as a map is left
    expect(clampPanel(99999, 1600)).toBe(1240);
  });

  it('is resizable in BOTH directions between those limits', () => {
    const wide = clampPanel(1100, 1600);
    const narrow = clampPanel(400, 1600);
    expect(wide).toBe(1100);
    expect(narrow).toBe(400);
    expect(wide).toBeGreaterThan(narrow);
  });

  it('passes a sane width through untouched', () => {
    expect(clampPanel(420, 1600)).toBe(420);
  });

  // On a narrow window the floor and the ceiling cross. The reader's floor
  // wins there: a 500px window cannot show both, and the pane you opened
  // deliberately is the one to keep.
  it('keeps the reader readable when the window is too small for both', () => {
    expect(clampPanel(400, 500)).toBe(280);
  });
});

describe('neighbours', () => {
  const edges = [
    { source: 'a', target: 'b', weight: 0.42 },
    { source: 'c', target: 'a', weight: 0.88 },
    { source: 'b', target: 'c', weight: 0.5 },
  ];

  it('reads an edge from either end, and returns the other paper', () => {
    expect(neighbours('a', edges)).toEqual([
      { id: 'c', weight: 0.88 },
      { id: 'b', weight: 0.42 },
    ]);
  });

  it('puts the strongest link first, since that is the one worth reading next', () => {
    expect(neighbours('c', edges).map((n) => n.id)).toEqual(['a', 'b']);
  });

  it('says nothing rather than guessing for an unlinked paper', () => {
    expect(neighbours('z', edges)).toEqual([]);
    expect(neighbours('a', undefined)).toEqual([]);
  });
});

describe('nearestFurthest', () => {
  // Positions are the server's PCA projection, normalised 0..1.
  const nodes = [
    { doc_id: 'a', x: 0.1, y: 0.1 },
    { doc_id: 'near', x: 0.15, y: 0.1 },
    { doc_id: 'mid', x: 0.5, y: 0.5 },
    { doc_id: 'far', x: 0.9, y: 0.9 },
  ];

  it('names the closest and the most distant paper in the projection', () => {
    const r = nearestFurthest(nodes[0], nodes);
    expect(r.near.doc_id).toBe('near');
    expect(r.far.doc_id).toBe('far');
  });

  it('never compares a paper with itself', () => {
    const r = nearestFurthest(nodes[2], nodes);
    expect(r.near.doc_id).not.toBe('mid');
    expect(r.far.doc_id).not.toBe('mid');
  });

  // One paper has no layout to explain -- PCA over a single point says nothing.
  it('returns null when there is nothing to compare against', () => {
    expect(nearestFurthest(nodes[0], [nodes[0]])).toBe(null);
  });

  // With exactly one other paper, near and far are the same paper, and
  // "closest to X, furthest from X" is nonsense. There is no far.
  it('has no furthest paper when only one other exists', () => {
    const r = nearestFurthest(nodes[0], [nodes[0], nodes[1]]);
    expect(r.near.doc_id).toBe('near');
    expect(r.far).toBe(null);
  });
});

/**
 * A gap connects papers, and you could only ever read it in one of them.
 *
 * The panel listed its evidence, and separately listed the papers it cites, and
 * clicking a paper lost the gap entirely -- you landed on the About tab with no
 * indication which passage was the evidence. This resolves the two lists into
 * one: for each cited paper, the passage in it that the gap rests on.
 */
describe('gapPassages', () => {
  const chunksA = [
    { chunk_id: 'a1', text: 'Unrelated opening remarks about the dataset.' },
    { chunk_id: 'a2', text: 'Existing methods rely on manually engineered molecular representation. They do not scale.' },
  ];
  const chunksB = [
    { chunk_id: 'b1', text: 'No model evaluates interactions between substructures of the two drugs.' },
  ];
  const gap = {
    doc_ids: ['A', 'B', 'C'],
    evidence: [
      'methods rely on manually engineered representation',
      'no model evaluates substructure interactions',
    ],
  };
  const texts = new Map([['A', chunksA], ['B', chunksB]]);

  it('finds the passage the gap rests on in each paper', () => {
    const found = gapPassages(gap, texts);
    expect(found.find((p) => p.docId === 'A').passage.text)
      .toBe('Existing methods rely on manually engineered molecular representation.');
  });

  // The first evidence phrase belongs to paper A, the second to paper B; a
  // panel that only tried the first would show B as having nothing.
  it('tries every evidence phrase, not only the first', () => {
    const found = gapPassages(gap, texts);
    expect(found.find((p) => p.docId === 'B').passage.text)
      .toBe('No model evaluates interactions between substructures of the two drugs.');
  });

  // Otherwise the panel offers a link that goes nowhere, which is worse than
  // saying plainly that the evidence could not be located.
  it('says nothing rather than guessing for a paper whose text has not loaded', () => {
    expect(gapPassages(gap, texts).find((p) => p.docId === 'C').passage).toBe(null);
  });

  it('keeps every cited paper, located or not', () => {
    expect(gapPassages(gap, texts).map((p) => p.docId)).toEqual(['A', 'B', 'C']);
  });

  it('carries the chunk so the reader can be opened at it', () => {
    expect(gapPassages(gap, texts).find((p) => p.docId === 'A').passage.chunkId).toBe('a2');
  });

  it('survives a gap with no evidence and no papers', () => {
    expect(gapPassages({ doc_ids: ['A'], evidence: [] }, texts)[0].passage).toBe(null);
    expect(gapPassages(null, texts)).toEqual([]);
  });
});

/**
 * The local graph. A chain plus one branch, so a paper is reachable at more
 * than one depth and the shortest one has to win:
 *
 *   a -- b -- c -- d
 *   |         |
 *   e         f
 */
describe('localGraph', () => {
  const edges = [
    { source: 'a', target: 'b', weight: 0.8 },
    { source: 'b', target: 'c', weight: 0.7 },
    { source: 'c', target: 'd', weight: 0.6 },
    { source: 'a', target: 'e', weight: 0.5 },
    { source: 'c', target: 'f', weight: 0.4 },
  ];

  it('depth 1 is the papers this one is linked to', () => {
    const hop = localGraph('a', edges, 1);
    expect([...hop.keys()].sort()).toEqual(['a', 'b', 'e']);
    expect(hop.get('a')).toBe(0);
    expect(hop.get('b')).toBe(1);
  });

  it('depth 2 adds what those are linked to', () => {
    const hop = localGraph('a', edges, 2);
    expect([...hop.keys()].sort()).toEqual(['a', 'b', 'c', 'e']);
    expect(hop.get('c')).toBe(2);
  });

  it('depth 3 reaches round the corner', () => {
    const hop = localGraph('a', edges, 3);
    expect([...hop.keys()].sort()).toEqual(['a', 'b', 'c', 'd', 'e', 'f']);
    expect(hop.get('d')).toBe(3);
    expect(hop.get('f')).toBe(3);
  });

  it('records the shortest hop, not the last one found', () => {
    // Reached from b at 1 and from e at 2; the ring it is drawn in is 1.
    const hop = localGraph('b', [...edges, { source: 'e', target: 'c', weight: 0.3 }], 3);
    expect(hop.get('c')).toBe(1);
  });

  it('reads an edge from whichever end the paper sits on', () => {
    // The edge list is undirected, and every one of these has `a` as source.
    expect([...localGraph('e', edges, 1).keys()].sort()).toEqual(['a', 'e']);
  });

  it('an orphan is alone, and is still in its own map', () => {
    const hop = localGraph('z', edges, 3);
    expect([...hop.keys()]).toEqual(['z']);
    expect(hop.get('z')).toBe(0);
  });

  it('stops early rather than looping when the walk runs out', () => {
    // Depth 9 on a graph five hops wide must terminate, and must not revisit.
    const hop = localGraph('a', edges, 9);
    expect(hop.size).toBe(6);
  });

  it('survives an empty or missing edge list', () => {
    expect([...localGraph('a', [], 2).keys()]).toEqual(['a']);
    expect([...localGraph('a', undefined, 2).keys()]).toEqual(['a']);
  });
});
