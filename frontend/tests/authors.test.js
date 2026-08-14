/**
 * The separator rule for the Library's reference editor.
 *
 * The whole feature exists because `", ".join(authors)` destroyed author
 * lists, so the one thing this parser must never do is destroy one the same
 * way on the way back in.
 */
import { describe, it, expect } from 'vitest';
import { splitAuthors } from '../src/utils/authors';

describe('splitAuthors', () => {
  it('splits the ordinary comma-separated list', () => {
    expect(splitAuthors('Ada Lovelace, Alan Turing'))
      .toEqual(['Ada Lovelace', 'Alan Turing']);
  });

  it('leaves a surname-first name whole when semicolons are used', () => {
    expect(splitAuthors('Vaswani, Ashish; Shazeer, Noam'))
      .toEqual(['Vaswani, Ashish', 'Shazeer, Noam']);
  });

  it('trims and drops the empties a trailing separator leaves', () => {
    expect(splitAuthors('  Ada Lovelace ,, Alan Turing,  '))
      .toEqual(['Ada Lovelace', 'Alan Turing']);
  });

  it('reads a single name as one author', () => {
    expect(splitAuthors('Allen B. Downey')).toEqual(['Allen B. Downey']);
  });

  it('gives an empty list for an empty field', () => {
    expect(splitAuthors('')).toEqual([]);
    expect(splitAuthors('   ')).toEqual([]);
    expect(splitAuthors(null)).toEqual([]);
  });
});
