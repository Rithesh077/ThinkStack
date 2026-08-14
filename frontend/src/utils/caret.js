/**
 * Where the caret is, in pixels, inside a <textarea>.
 *
 * A textarea has no API for this. `selectionStart` is a character offset and
 * nothing on the element converts one into coordinates, which is the usual
 * reason editors that need a caret-anchored popup reach for CodeMirror.
 *
 * The way around it is a mirror: an off-screen div wearing the textarea's own
 * computed styles, holding the text up to the caret and then a marker span.
 * The browser lays that out with the same font, wrapping and padding, so the
 * marker lands where the caret is and its offset is the answer.
 *
 * The styles below are copied rather than inherited because the mirror is not
 * a child of the textarea -- it cannot be, a textarea has no element children.
 * Any property that changes where a glyph falls has to be on this list.
 */

const MIRRORED = [
  'boxSizing', 'width', 'borderTopWidth', 'borderRightWidth',
  'borderBottomWidth', 'borderLeftWidth', 'paddingTop', 'paddingRight',
  'paddingBottom', 'paddingLeft', 'fontStyle', 'fontVariant', 'fontWeight',
  'fontStretch', 'fontSize', 'fontFamily', 'lineHeight', 'letterSpacing',
  'wordSpacing', 'textIndent', 'textTransform', 'tabSize', 'whiteSpace',
  'wordWrap', 'overflowWrap', 'wordBreak',
];

/**
 * `{ top, left, height }` relative to the textarea's own box, scrolling
 * accounted for. A caret scrolled out of view returns a negative `top`, which
 * is a true answer -- the caller decides whether to show anything there.
 */
export function caretCoords(textarea, index) {
  const style = window.getComputedStyle(textarea);
  const mirror = document.createElement('div');

  for (const prop of MIRRORED) mirror.style[prop] = style[prop];
  mirror.style.position = 'absolute';
  mirror.style.visibility = 'hidden';
  mirror.style.top = '0';
  mirror.style.left = '0';
  // A textarea always wraps and always scrolls vertically; the mirror has to
  // agree on both or the wrap points drift apart line by line.
  mirror.style.whiteSpace = 'pre-wrap';
  mirror.style.overflowWrap = 'break-word';
  mirror.style.height = 'auto';

  mirror.textContent = textarea.value.slice(0, index);

  const marker = document.createElement('span');
  // A zero-width span collapses onto the previous line's end when the caret
  // sits at a wrap point. A real character occupies the position the caret
  // would, so the marker wraps when the caret does.
  marker.textContent = textarea.value.slice(index) || '.';
  mirror.appendChild(marker);

  document.body.appendChild(mirror);
  const top = marker.offsetTop - textarea.scrollTop;
  const left = marker.offsetLeft - textarea.scrollLeft;
  const height = parseFloat(style.lineHeight) || marker.offsetHeight;
  document.body.removeChild(mirror);

  return { top, left, height };
}
