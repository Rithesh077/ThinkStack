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
import { inTauri, pickProjectFile } from '../utils/filePicker';

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
  // the typed-path fallback, for running in a browser where there is no
  // native dialog to open. Not dead weight: it is also the way in for a file
  // that lives somewhere a dialog makes awkward to reach.
  const [typing, setTyping] = useState(null);

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

  /** ask natively where possible, fall back to typing a path */
  const choose = async (then, opts) => {
    const { path, reason } = await pickProjectFile(opts);
    if (path) return then(path);
    if (reason === 'cancelled') return undefined;
    // No native dialog: this is a browser, where a file input hands back bytes
    // and deliberately withholds the path. Typing it is the way through, and
    // is also the escape hatch for a file somewhere a dialog makes awkward.
    return setTyping({ then });
  };

  const add = (directory = false) =>
    choose((path) => run(() => projectFilesApi.addLink(projectId, path)), { directory });

  const locate = (link) =>
    choose(
      (path) => run(() => projectFilesApi.relink(projectId, link.id, path)),
      { directory: link.kind === 'dir' },
    );

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

      {typing && (
        <div className="lf-typed">
          <input
            className="ft-rename"
            autoFocus
            placeholder={inTauri() ? 'full path' : '/home/you/paper/refs.bib'}
            onKeyDown={(e) => {
              e.stopPropagation();
              if (e.key === 'Enter') {
                const v = e.target.value.trim();
                setTyping(null);
                if (v) typing.then(v);
              }
              if (e.key === 'Escape') setTyping(null);
            }}
            onBlur={() => setTyping(null)}
          />
        </div>
      )}

      {!links.length && !typing && (
        <p className="lf-empty">
          Nothing linked. Use + for a file, or the folder button for a whole
          directory, kept elsewhere on this machine.
        </p>
      )}
      {error && <p className="ft-error">{error}</p>}
    </div>
  );
}
