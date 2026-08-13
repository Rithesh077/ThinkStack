/**
 * Ask before doing something that cannot be undone.
 *
 * Deliberately not a toast. A toast reports something that already happened and
 * dismisses itself; a destructive action needs an answer, and an answer cannot
 * time out. This is also why it is not the browser's `confirm()`: ThinkStack
 * runs in a Tauri webview, where `confirm()` is not implemented and returns
 * undefined -- so a guard written as `if (!confirm(...)) return` either blocks
 * the action forever or, read the other way, deletes without ever asking.
 *
 * Shared, because this was about to be the third dialog in the codebase:
 * Library inlines its own overlay as style props, LitGraph has `.lg-modal`, and
 * the file tree needed one too. Three dialogs means three sets of behaviour to
 * get right -- Escape, click-outside, focus, the destructive button being the
 * one that is NOT focused by default.
 *
 * Cancel takes focus on open, not Delete: this is the last thing standing
 * between a paper and oblivion, and a stray Enter should not be what crosses it.
 *
 * `children` finishes the consolidation the note above only started. Library's
 * encryption modal was the third dialog -- an overlay hand-built from style
 * props, with no Escape key, no focus management and no guard against a drag
 * that begins inside the box and ends on the backdrop. Passing children turns
 * this into the dialog *chrome* and lets the caller own the contents, so a form
 * gets the behaviour without the confirm-shaped footer it has no use for. When
 * children are present the caller's own `autoFocus` is left alone, because a
 * password field that has to be reached by tabbing is worse than useless.
 */

import { useEffect, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';

export default function ConfirmDialog({
  title,
  body,
  children,
  icon: Icon = AlertTriangle,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  danger = true,
  onConfirm,
  onCancel,
  wide = false,
}) {
  const cancelRef = useRef(null);
  // a boolean, not `children` itself: a JSX element is a fresh object every
  // render, so depending on it would tear down and re-add the key listener on
  // every keystroke typed into the form it is wrapping
  const custom = Boolean(children);

  useEffect(() => {
    if (!custom) cancelRef.current?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onCancel?.(); }
    };
    document.addEventListener('keydown', onKey, true);
    return () => document.removeEventListener('keydown', onKey, true);
  }, [onCancel, custom]);

  return (
    <div
      className="confirm-overlay"
      role="presentation"
      onPointerDown={(e) => {
        // only a press on the backdrop itself dismisses; a press that started
        // inside the box and drifted out must not count as "cancel"
        if (e.target === e.currentTarget) onCancel?.();
      }}
    >
      <div
        className={`confirm-box ${wide ? 'is-wide' : ''}`.trim()}
        role={custom ? 'dialog' : 'alertdialog'}
        aria-modal="true"
        aria-label={title}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <div className="confirm-head">
          {(danger || custom) && <Icon size={16} className="confirm-icon" />}
          <h3>{title}</h3>
        </div>
        {children ?? (
          <>
            {body && <p>{body}</p>}
            <div className="confirm-actions">
              <button type="button" ref={cancelRef} className="btn btn-secondary" onClick={onCancel}>
                {cancelLabel}
              </button>
              <button
                type="button"
                className={`btn ${danger ? 'btn-danger' : 'btn-primary'}`}
                onClick={onConfirm}
              >
                {confirmLabel}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
