/**
 * Choose a file or a folder by navigating to it.
 *
 * The native dialog only exists inside the desktop shell. In a browser there is
 * none, and a file input hands back bytes with the path withheld -- so the
 * fallback used to be typing a path, which is not choosing, it is remembering.
 *
 * This is the same chooser everywhere. One behaviour to learn, one code path to
 * test, and it works in the window and in a tab.
 *
 * Keys follow the editor they remind people of: Enter opens a folder or takes a
 * file, Backspace goes up, Escape leaves. The caller binds Ctrl+O and
 * Ctrl+K Ctrl+O to open it in the two modes.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  ArrowUp, CornerDownLeft, FileText, FolderClosed, Home, Loader2, Search, X,
} from 'lucide-react';
import { projectFilesApi } from '../utils/api';

function human(n) {
  if (n === undefined || n === null) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function PathPicker({ mode = 'file', onPick, onCancel }) {
  const wantFolder = mode === 'folder';
  const [cwd, setCwd] = useState(null);
  const [entries, setEntries] = useState([]);
  const [parent, setParent] = useState(null);
  const [home, setHome] = useState(null);
  const [filter, setFilter] = useState('');
  const [cursor, setCursor] = useState(0);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const listRef = useRef(null);

  const go = useCallback(async (path) => {
    setLoading(true);
    setError(null);
    try {
      const r = await projectFilesApi.browse(path);
      setCwd(r.path);
      setParent(r.parent);
      setHome(r.home);
      setEntries(r.entries || []);
      setCursor(0);
      setFilter('');
    } catch (e) {
      // a folder that cannot be opened says so and stays put, rather than
      // showing an empty list that reads as "nothing here"
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { go(''); }, [go]);

  const shown = entries.filter((e) => {
    if (filter && !e.name.toLowerCase().includes(filter.toLowerCase())) return false;
    if (wantFolder) return e.is_dir;      // choosing a folder: files are noise
    return true;
  });

  const canTake = (e) => (wantFolder ? e.is_dir : !e.is_dir && e.linkable);

  const activate = (e) => {
    if (!e) return;
    if (e.is_dir && !wantFolder) return go(e.path);
    if (e.is_dir && wantFolder) return go(e.path);   // navigate; "Use this" takes it
    if (canTake(e)) return onPick(e.path);
    return undefined;
  };

  const onKey = (ev) => {
    if (ev.key === 'Escape') { ev.preventDefault(); return onCancel(); }
    if (ev.key === 'ArrowDown') { ev.preventDefault(); return setCursor((c) => Math.min(c + 1, shown.length - 1)); }
    if (ev.key === 'ArrowUp') { ev.preventDefault(); return setCursor((c) => Math.max(c - 1, 0)); }
    if (ev.key === 'Backspace' && !filter && parent) { ev.preventDefault(); return go(parent); }
    if (ev.key === 'Enter') { ev.preventDefault(); return activate(shown[cursor]); }
    return undefined;
  };

  useEffect(() => {
    const el = listRef.current?.children?.[cursor];
    if (el?.scrollIntoView) el.scrollIntoView({ block: 'nearest' });
  }, [cursor]);

  return (
    <div className="pp-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="pp" role="dialog" aria-label={wantFolder ? 'Choose a folder' : 'Choose a file'}>
        <div className="pp-head">
          <span className="pp-title">
            {wantFolder ? 'Choose a folder' : 'Choose a file'}
          </span>
          <button type="button" onClick={onCancel} title="Close"><X size={13} /></button>
        </div>

        <div className="pp-bar">
          <button type="button" onClick={() => go(home)} title="Home" disabled={!home}>
            <Home size={12} />
          </button>
          <button type="button" onClick={() => parent && go(parent)} title="Up one folder" disabled={!parent}>
            <ArrowUp size={12} />
          </button>
          <span className="pp-cwd" title={cwd || ''}>{cwd || '…'}</span>
        </div>

        <div className="pp-filter">
          <Search size={11} />
          <input
            autoFocus
            value={filter}
            placeholder="Type to narrow"
            onChange={(e) => { setFilter(e.target.value); setCursor(0); }}
            onKeyDown={onKey}
          />
        </div>

        <div className="pp-list" ref={listRef}>
          {loading && <p className="pp-note"><Loader2 size={12} className="ft-spin" /> reading…</p>}
          {!loading && error && <p className="pp-error">{error}</p>}
          {!loading && !error && shown.map((e, i) => (
            <button
              type="button"
              key={e.path}
              className={`pp-row ${i === cursor ? 'is-cursor' : ''} ${canTake(e) || e.is_dir ? '' : 'is-off'}`}
              onMouseEnter={() => setCursor(i)}
              onDoubleClick={() => activate(e)}
              onClick={() => (e.is_dir ? go(e.path) : canTake(e) && onPick(e.path))}
            >
              {e.is_dir ? <FolderClosed size={12} /> : <FileText size={12} />}
              <span className="pp-name">{e.name}</span>
              <span className="pp-size">{e.is_dir ? '' : human(e.size)}</span>
            </button>
          ))}
          {!loading && !error && !shown.length && (
            <p className="pp-note">
              {wantFolder ? 'No folders here.' : 'Nothing here a paper can use.'}
            </p>
          )}
        </div>

        <div className="pp-foot">
          <span className="pp-hint">
            <CornerDownLeft size={10} /> open · Backspace up · Esc cancel
          </span>
          {wantFolder && (
            <button type="button" className="pp-take" onClick={() => cwd && onPick(cwd)} disabled={!cwd}>
              Use this folder
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
