/**
 * Files a paper uses that live somewhere else on the machine.
 *
 * The rule this follows is the one the model registry already follows: a link
 * REFERENCES a file where it sits rather than taking a copy. Someone with a
 * 40MB PDF should not acquire a second one because the application preferred a
 * tidy folder, and a .bib shared between three papers should be one file that
 * stays in step with itself.
 *
 * The price is that a referenced file can move, so the interesting states here
 * are the unhappy ones. Each link reports one of three:
 *
 *   ok       where we left it
 *   moved    found again by its filesystem identity; the path has been updated
 *   missing  the honest answer, with a button to point us at it
 *
 * "missing" is deliberately not silent and deliberately not a guess. A tree
 * that quietly drops an entry is worse than one that admits it lost track.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, Copy, FolderClosed, FolderPlus, Link2, Link2Off,
  Loader2, MoveRight, Plus,
} from 'lucide-react';
import { projectFilesApi } from '../utils/api';
import PathPicker from './PathPicker';

function human(bytes) {
  if (!bytes && bytes !== 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function LinkedFiles({ projectId, onFilesChanged }) {
  const [links, setLinks] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // What the chooser is currently for: linking something new, or repairing a
  // link whose file moved. Held together because both end in a path and the
  // window is the same window.
  const [picking, setPicking] = useState(null);   // { mode, then }

  const load = useCallback(async () => {
    try {
      const r = await projectFilesApi.links(projectId);
      setLinks(r.links || []);
    } catch (e) {
      setError(e.message);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const run = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      if (r?.links) setLinks(r.links);
      if (r?.files && onFilesChanged) onFilesChanged(r.files);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  /* One chooser, everywhere. The native dialog was only ever available inside
     the desktop shell, and its absence in a browser left typing a path as the
     way through -- which is remembering, not choosing. PathPicker reads
     directories through the backend, so the same window opens in the app and in
     a tab. */
  const add = (directory = false) =>
    setPicking({
      mode: directory ? 'folder' : 'file',
      then: (path) => run(() => projectFilesApi.addLink(projectId, path)),
    });

  const locate = (link) =>
    setPicking({
      mode: link.kind === 'dir' ? 'folder' : 'file',
      then: (path) => run(() => projectFilesApi.relink(projectId, link.id, path)),
    });

  /* The keys this borrows from, because they are the ones in people's hands:
     Ctrl+O for a file, Ctrl+K Ctrl+O for a folder. The chord waits a moment for
     its second key and then forgets, so a stray Ctrl+K does not arm a trap. */
  useEffect(() => {
    let chord = false;
    let timer = null;
    const onKey = (e) => {
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      if (chord && e.key.toLowerCase() === 'o') {
        e.preventDefault();
        chord = false;
        clearTimeout(timer);
        return add(true);
      }
      if (e.key.toLowerCase() === 'k') {
        chord = true;
        clearTimeout(timer);
        timer = setTimeout(() => { chord = false; }, 1500);
        return undefined;
      }
      if (e.key.toLowerCase() === 'o') {
        e.preventDefault();
        return add(false);
      }
      return undefined;
    };
    window.addEventListener('keydown', onKey);
    return () => { window.removeEventListener('keydown', onKey); clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  return (
    <div className="lf">
      <div className="lf-head">
        <span className="lf-title">
          <Link2 size={11} /> Linked
        </span>
        <span className="lf-head-actions">
          <button
            type="button"
            onClick={() => add(false)}
            disabled={busy}
            title="Link a file kept elsewhere"
          >
            {busy ? <Loader2 size={12} className="ft-spin" /> : <Plus size={12} />}
          </button>
          <button
            type="button"
            onClick={() => add(true)}
            disabled={busy}
            title="Link a folder kept elsewhere"
          >
            <FolderPlus size={12} />
          </button>
        </span>
      </div>

      {links.map((l) => (
        <div key={l.id} className={`lf-row is-${l.status}`}>
          <span className="lf-name" title={l.resolved || l.path}>
            {l.kind === 'dir' && <FolderClosed size={10} className="lf-kind" />}
            {l.name}
          </span>
          <span className="lf-meta">
            {l.status === 'missing' && (
              <span className="lf-warn"><AlertTriangle size={10} /> missing</span>
            )}
            {l.status === 'moved' && (
              <span className="lf-moved" title={`now at ${l.resolved}`}>
                <MoveRight size={10} /> moved
              </span>
            )}
            {l.status === 'ok' && (l.kind === 'dir' ? 'folder' : human(l.size))}
          </span>
          <span className="lf-actions">
            {l.status === 'missing' ? (
              <button type="button" title="Find it" onClick={() => locate(l)}>
                Locate
              </button>
            ) : (
              <button
                type="button"
                title="Copy into this paper"
                onClick={() => run(() => projectFilesApi.copyLinkIn(projectId, l.id))}
              >
                <Copy size={11} />
              </button>
            )}
            <button
              type="button"
              title="Forget this link. The file itself is not deleted."
              onClick={() => run(() => projectFilesApi.unlink(projectId, l.id))}
            >
              <Link2Off size={11} />
            </button>
          </span>
        </div>
      ))}

      {picking && (
        <PathPicker
          mode={picking.mode}
          onCancel={() => setPicking(null)}
          onPick={(path) => { const { then } = picking; setPicking(null); then(path); }}
        />
      )}

      {!links.length && (
        <p className="lf-empty">
          Nothing linked. Use + for a file, or the folder button for a whole
          directory, kept elsewhere on this machine.
        </p>
      )}
      {error && <p className="ft-error">{error}</p>}
    </div>
  );
}
