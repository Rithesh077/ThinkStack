/**
 * What this document cites, and whether each citation will resolve.
 *
 * `references.bib` says what COULD be cited; the source says what IS. They
 * drift in both directions and neither drift was visible: to see the
 * references at all you had to open the .bib in the tree or compile and read
 * the PDF.
 *
 * Three states, and the two unhappy ones are the reason this exists:
 *
 *   ok       cited, and defined in references.bib
 *   missing  cited but NOT defined -- this renders as [?] in the PDF, which is
 *            how the question-mark bug was reported in the first place
 *   unused   defined but never cited, carried around forever
 *
 * Collapsed by default. It is a thing you consult, not a thing you read while
 * writing, and the editor should not lose height to it unasked.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, BookMarked, ChevronDown, ChevronRight, ExternalLink,
} from 'lucide-react';
import { projectFilesApi } from '../utils/api';

export default function BibliographyPanel({ projectId, source, onOpenPaper }) {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    if (!projectId) return;
    try {
      setData(await projectFilesApi.bibliography(projectId));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [projectId]);

  // Reloads when the source changes, because a citation typed a moment ago
  // should appear here without a compile -- that is the point of reading the
  // source rather than the PDF.
  useEffect(() => { if (open) load(); }, [open, load, source]);
  useEffect(() => { load(); }, [load]);

  const entries = data?.entries || [];
  const unused = data?.unused || [];
  const missing = entries.filter((e) => e.status === 'missing').length;

  return (
    <div className={`bib ${open ? 'is-open' : ''}`}>
      <button type="button" className="bib-head" onClick={() => setOpen((v) => !v)}>
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <BookMarked size={12} />
        <span className="bib-title">References</span>
        <span className="bib-counts">
          {entries.length > 0 && <span>{entries.length} cited</span>}
          {missing > 0 && (
            <span className="bib-warn" title="These render as [?] in the PDF">
              <AlertTriangle size={10} /> {missing} missing
            </span>
          )}
          {unused.length > 0 && <span className="bib-quiet">{unused.length} unused</span>}
          {entries.length === 0 && unused.length === 0 && <span className="bib-quiet">none</span>}
        </span>
      </button>

      {open && (
        <div className="bib-body">
          {error && <p className="bib-error">{error}</p>}

          {entries.map((e) => (
            <div key={e.key} className={`bib-row is-${e.status}`}>
              <code className="bib-key">{e.key}</code>
              <span className="bib-what">
                {e.title || <em>not in your library</em>}
                {e.year ? ` (${e.year})` : ''}
              </span>
              {e.count > 1 && <span className="bib-times" title="times cited">×{e.count}</span>}
              {e.status === 'missing' && (
                <span className="bib-warn" title="Not in references.bib — renders as [?]">
                  <AlertTriangle size={10} />
                </span>
              )}
              {e.doc_id && onOpenPaper && (
                <button
                  type="button"
                  title="Open this paper in Library"
                  onClick={() => onOpenPaper(e.doc_id)}
                >
                  <ExternalLink size={11} />
                </button>
              )}
            </div>
          ))}

          {unused.length > 0 && (
            <div className="bib-unused">
              <span className="bib-unused-label">In references.bib but never cited</span>
              {unused.map((k) => <code key={k} className="bib-key">{k}</code>)}
            </div>
          )}

          {!entries.length && !unused.length && !error && (
            <p className="bib-empty">
              Nothing cited yet. Type <code>cite</code> in the editor to add one.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
