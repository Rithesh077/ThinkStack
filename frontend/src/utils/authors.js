/**
 * Reading a typed author list back into names.
 *
 * Semicolons first, commas second. `Vaswani, Ashish` is one person written
 * surname-first, and splitting that on the comma is the exact mistake this
 * editor exists to repair -- so a semicolon anywhere in the line means the
 * author reached for the unambiguous separator and their commas are part of
 * the names.
 *
 * Commas stay the default because that is what almost every author list looks
 * like, and what the field shows when it opens.
 */
export function splitAuthors(text) {
  const line = String(text || '');
  return line
    .split(line.includes(';') ? ';' : ',')
    .map((a) => a.trim())
    .filter(Boolean);
}
