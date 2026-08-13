/**
 * Earned colour.
 *
 * The app ships grey and each pigment is granted by the one thing it names.
 * What matters here is not that a colour appears -- it is that it never
 * un-appears. A pigment that came back grey after a reload, or after the user
 * deleted the paper that earned it, would turn a reward into a punishment for
 * tidying up. So most of what follows is checking that earning is permanent,
 * idempotent, and survives storage being unavailable.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  earn, earned, hasEarned, applyEarned, backfill, __resetPigments, EARNED_BY,
  mode, setMode, visible, shouldAnnounce, PIGMENT_EARNED, PIGMENTS,
} from '../src/utils/pigments';

const KEY = 'thinkstack.pigments';

beforeEach(() => {
  localStorage.clear();
  __resetPigments();
});

describe('a fresh install', () => {
  it('has earned nothing', () => {
    expect(earned()).toEqual([]);
    expect(hasEarned('mark')).toBe(false);
  });

  it('paints an empty attribute rather than leaving it unset', () => {
    // The stylesheet matches [data-earned~="..."], so an absent attribute and
    // an empty one behave the same -- but an empty one proves we ran.
    applyEarned();
    expect(document.documentElement.getAttribute('data-earned')).toBe('');
  });
});

describe('earning a pigment', () => {
  it('persists it and puts it on <html>', () => {
    expect(earn('ochre')).toBe(true);
    expect(localStorage.getItem(KEY)).toBe('ochre');
    expect(document.documentElement.getAttribute('data-earned')).toBe('ochre');
  });

  it('reports false the second time, and does not duplicate it', () => {
    earn('ochre');
    expect(earn('ochre')).toBe(false);
    expect(earned()).toEqual(['ochre']);
  });

  it('accumulates into one space-separated attribute', () => {
    earn('ochre');
    earn('moss');
    earn('mark');
    expect(document.documentElement.getAttribute('data-earned')).toBe('ochre moss mark');
  });

  it('ignores a name that is not a pigment', () => {
    expect(earn('chartreuse')).toBe(false);
    expect(earned()).toEqual([]);
  });

  it('survives a reload', () => {
    earn('slate');
    document.documentElement.removeAttribute('data-earned');
    applyEarned();
    expect(document.documentElement.getAttribute('data-earned')).toBe('slate');
  });

  it('names the red pen after finding a gap, not after anything else', () => {
    expect(EARNED_BY.gapFound).toBe('mark');
    expect(Object.values(EARNED_BY).filter((p) => p === 'mark')).toHaveLength(1);
  });
});

describe('when localStorage throws', () => {
  it('still paints the pigment for this session', () => {
    const setItem = Storage.prototype.setItem;
    Storage.prototype.setItem = () => { throw new Error('private mode'); };
    try {
      expect(earn('mark')).toBe(true);
      expect(document.documentElement.getAttribute('data-earned')).toBe('mark');
    } finally {
      Storage.prototype.setItem = setItem;
    }
  });

  it('reads as a fresh install rather than crashing', () => {
    const getItem = Storage.prototype.getItem;
    Storage.prototype.getItem = () => { throw new Error('private mode'); };
    try {
      expect(earned()).toEqual([]);
    } finally {
      Storage.prototype.getItem = getItem;
    }
  });
});

/**
 * The record and the lens.
 *
 * The mode is how much of the record the reader wants painted, and it must
 * never be a way to rewrite the record. The test that matters is the round
 * trip: take the full set on day one, go back to earning later, and you get
 * exactly what you actually earned -- not everything, and not nothing.
 */
describe('choosing how colour arrives', () => {
  it('earns by default, which is what the app was built for', () => {
    expect(mode()).toBe('earn');
    expect(shouldAnnounce()).toBe(true);
  });

  it('inks the full set on request without touching the record', () => {
    earn('ochre');
    setMode('full');
    expect(visible()).toEqual(PIGMENTS);
    expect(document.documentElement.getAttribute('data-earned'))
      .toBe('ochre moss slate mark');
    // The record is still one pigment long.
    expect(earned()).toEqual(['ochre']);
  });

  it('gives back the real earned set when the lens comes off', () => {
    earn('ochre');
    setMode('full');
    earn('moss');            // genuinely earned while the full set was showing
    setMode('earn');
    expect(visible()).toEqual(['ochre', 'moss']);
    expect(document.documentElement.getAttribute('data-earned')).toBe('ochre moss');
  });

  it('keeps earning underneath while staying grey', () => {
    setMode('grey');
    expect(earn('mark')).toBe(true);
    expect(visible()).toEqual([]);
    expect(document.documentElement.getAttribute('data-earned')).toBe('');
    // The act was still recorded, so switching back shows it.
    setMode('earn');
    expect(visible()).toEqual(['mark']);
  });

  it('ignores a mode that does not exist', () => {
    setMode('sepia');
    expect(mode()).toBe('earn');
  });

  it('announces only when there is something to see', () => {
    setMode('full');
    expect(shouldAnnounce()).toBe(false);
    setMode('grey');
    expect(shouldAnnounce()).toBe(false);
    setMode('earn');
    expect(shouldAnnounce()).toBe(true);
  });
});

describe('the ceremony', () => {
  it('fires once, on the call that earned the pigment', () => {
    const seen = [];
    const onEarned = (e) => seen.push(e.detail);
    window.addEventListener(PIGMENT_EARNED, onEarned);
    try {
      earn('slate');
      earn('slate');   // already earned: nothing to announce
      expect(seen).toEqual(['slate']);
    } finally {
      window.removeEventListener(PIGMENT_EARNED, onEarned);
    }
  });

  it('stays silent in the modes where there is nothing to announce', () => {
    const seen = [];
    const onEarned = (e) => seen.push(e.detail);
    window.addEventListener(PIGMENT_EARNED, onEarned);
    try {
      setMode('grey');
      earn('ochre');
      setMode('full');
      earn('moss');
      expect(seen).toEqual([]);
    } finally {
      window.removeEventListener(PIGMENT_EARNED, onEarned);
    }
  });
});

describe('backfilling an install that predates the feature', () => {
  it('grants what a populated library proves was already earned', () => {
    expect(backfill({ papers: 12, analyses: 3, gaps: 1 }).length).toBe(4);
    expect(hasEarned('ochre')).toBe(true);
    expect(hasEarned('slate')).toBe(true);
    expect(hasEarned('moss')).toBe(true);
    expect(hasEarned('mark')).toBe(true);
  });

  it('withholds the red pen from a library that has never found a gap', () => {
    backfill({ papers: 12, analyses: 3, gaps: 0 });
    expect(hasEarned('mark')).toBe(false);
  });

  it('does nothing on a genuinely empty library', () => {
    expect(backfill({ papers: 0, analyses: 0, gaps: 0 })).toEqual([]);
    expect(earned()).toEqual([]);
  });

  it('never overwrites a real milestone', () => {
    // Someone who earned the red pen first must not be reset to the
    // backfill's idea of what their library deserves.
    earn('mark');
    expect(backfill({ papers: 99, analyses: 99, gaps: 99 })).toEqual([]);
    expect(earned()).toEqual(['mark']);
  });
});
