import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Trash2, RefreshCw, ChevronDown, ChevronUp, ChevronLeft, ChevronRight,
         Lock, ShieldCheck, ShieldOff, Eye, EyeOff, Pencil, Search } from 'lucide-react';
import { documentsApi, encryptionApi, papersApi, registryApi, useJobs } from '../utils/api';
import { FEATURES } from '../features';
import { libraryTourOpen, setLibraryTourOpen } from '../utils/firstRun';
import UploadPanel from './UploadPanel';
import PageHeader from './PageHeader';
import ConfirmDialog from './ConfirmDialog';

// Everything except Library itself: this list sits ON Library, and a page does
// not introduce itself. Read from FEATURES so a new feature appears here
// without anyone remembering, and so the wording cannot drift from the "i".
const OTHER_FEATURES = FEATURES.filter((f) => f.id !== 'library');

// The routing table's task keys, in the words the rest of the app uses.
const TASK_LABELS = {
  general: 'General',
  analysis: 'Analysis',
  gap_analysis: 'Gap finding',
  latex_writer: 'LaTeX writing',
};

// Rows at once. Small on purpose: this page is meant to be taken in at a
// glance, and a list long enough to scroll buries whatever sits above it.
const PAGE_SIZE = 5;

/**
 * Library - the paper collection.
 *
 * displays all ingested documents, allows upload of new papers,
 * and provides document deletion and encryption controls.
 * shows metadata, chunk counts, and encryption status for each paper.
 */
export default function Library() {
  const navigate = useNavigate();
  // Expanded only for someone who has never run this app. An update should not
  // greet an existing user with an introduction to their own workspace.
  const [tourOpen, setTourOpen] = useState(libraryTourOpen);
  const toggleTour = () => setTourOpen((open) => { setLibraryTourOpen(!open); return !open; });

  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, total_chunks: 0, analyses: 0, gaps: 0 });
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(0);
  const [onlyIncomplete, setOnlyIncomplete] = useState(false);
  const [renamingDoc, setRenamingDoc] = useState(null);
  const [renameValue, setRenameValue] = useState('');

  // Analysis is queued AFTER the upload responds, so without this the reader is
  // told "read", opens LitGraph, finds it empty, and concludes it is broken.
  const jobs = useJobs();
  const wasBusy = useRef(false);

  // `null` means not loaded or the call failed -- rendered differently from
  // "nothing yet", because an outage and an empty shelf are different facts.
  const [scribeProjects, setScribeProjects] = useState(null);
  const [benchModels, setBenchModels] = useState(null);
  const [expandedDoc, setExpandedDoc] = useState(null);
  const [docDetails, setDocDetails] = useState({});

  // encryption state
  const [encryptingDoc, setEncryptingDoc] = useState(null);
  const [encryptPassword, setEncryptPassword] = useState('');
  const [encryptAction, setEncryptAction] = useState(null);
  const [encryptError, setEncryptError] = useState('');
  const [encryptBusy, setEncryptBusy] = useState(false);
  const [decryptedText, setDecryptedText] = useState(null);
  const [showPassword, setShowPassword] = useState(false);

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const data = await documentsApi.list();
      setDocuments(data.documents || []);
      setStats({
        total: data.total,
        total_chunks: data.total_chunks,
        analyses: data.analyses ?? 0,
        gaps: data.gaps ?? 0,
      });
    } catch (err) {
      console.error('failed to load documents:', err);
    }
    setLoading(false);
  }, []);

  const loadScribeProjects = useCallback(async () => {
    try {
      const d = await papersApi.list();
      setScribeProjects(d.projects || []);
    } catch (err) {
      console.error('failed to load scribe projects:', err);
      setScribeProjects(null);
    }
  }, []);

  const loadBenchModels = useCallback(async () => {
    try {
      const snap = await registryApi.get();
      // `routing`, not `models`. There is no single active model: work is
      // routed per task, and which entry serves one depends on every other
      // entry -- assignment, the memory free right now, rank. The backend
      // computes that and says so at routes_registry.py:186; deciding it again
      // here lets the two drift. One row per task.
      const routing = snap.routing || {};
      setBenchModels(
        Object.entries(routing)
          .filter(([, r]) => r?.label)
          .map(([task, r]) => ({ task, label: r.label })),
      );
    } catch (err) {
      console.error('failed to load bench routing:', err);
      setBenchModels(null);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
    loadScribeProjects();
    loadBenchModels();
  }, [loadDocuments, loadScribeProjects, loadBenchModels]);

  // Refresh on the queue's FALLING edge, not every poll: the counts only change
  // when a job ends, and re-fetching twice a second reloads the list under the
  // reader's cursor.
  useEffect(() => {
    if (wasBusy.current && !jobs.active) loadDocuments();
    wasBusy.current = jobs.active;
  }, [jobs.active, loadDocuments]);

  // A filter that leaves you on page four of one shows an empty list.
  useEffect(() => { setPage(0); }, [query, onlyIncomplete]);

  const startRename = (doc) => {
    setRenamingDoc(doc.doc_id);
    setRenameValue(doc.metadata?.title || doc.filename || '');
  };

  const submitRename = async (docId) => {
    const title = renameValue.trim();
    if (!title) return;
    // Optimistic: the write touches every chunk of the paper and the list is
    // refetched anyway. Waiting to redraw makes a local edit feel remote.
    setDocuments((docs) => docs.map((d) => (
      d.doc_id === docId ? { ...d, metadata: { ...d.metadata, title } } : d
    )));
    setRenamingDoc(null);
    try {
      await documentsApi.rename(docId, title);
    } catch (err) {
      console.error('failed to rename document:', err);
      loadDocuments();   // put the stored title back
    }
  };

  const handleDelete = async (docId) => {
    try {
      await documentsApi.delete(docId);
      loadDocuments();
    } catch (err) {
      console.error('failed to delete document:', err);
    }
  };

  const toggleExpand = async (docId) => {
    if (expandedDoc === docId) {
      setExpandedDoc(null);
      return;
    }
    setExpandedDoc(docId);
    if (!docDetails[docId]) {
      try {
        const details = await documentsApi.get(docId);
        setDocDetails((prev) => ({ ...prev, [docId]: details }));
      } catch (err) {
        console.error('failed to load document details:', err);
      }
    }
  };

  // --- Encryption handlers ---

  const openEncryptDialog = (docId, action) => {
    setEncryptingDoc(docId);
    setEncryptAction(action);
    setEncryptPassword('');
    setEncryptError('');
    setDecryptedText(null);
    setShowPassword(false);
  };

  const closeEncryptDialog = () => {
    setEncryptingDoc(null);
    setEncryptAction(null);
    setEncryptPassword('');
    setEncryptError('');
    setDecryptedText(null);
    setShowPassword(false);
  };

  const handleEncryptSubmit = async (e) => {
    e.preventDefault();
    if (!encryptPassword.trim()) {
      setEncryptError('password is required');
      return;
    }

    setEncryptBusy(true);
    setEncryptError('');

    try {
      if (encryptAction === 'encrypt') {
        await encryptionApi.encrypt(encryptingDoc, encryptPassword);
        closeEncryptDialog();
        loadDocuments();
      } else if (encryptAction === 'view') {
        const result = await encryptionApi.decrypt(encryptingDoc, encryptPassword);
        setDecryptedText(result.full_text);
      } else if (encryptAction === 'remove') {
        await encryptionApi.removeEncryption(encryptingDoc, encryptPassword);
        closeEncryptDialog();
        loadDocuments();
      }
    } catch (err) {
      setEncryptError(err.message || 'operation failed');
    }

    setEncryptBusy(false);
  };

  // All derived from the list already fetched -- no extra call, and no counter
  // that can disagree with the rows beneath it.
  const hasAuthors = (d) => /[a-z]/i.test(d.metadata?.authors || '');
  const incomplete = documents.filter((d) => !hasAuthors(d) || !d.metadata?.year);

  const matchesQuery = (doc) => {
    if (!query.trim()) return true;
    const m = doc.metadata || {};
    return `${m.title || ''} ${m.authors || ''} ${doc.filename || ''}`
      .toLowerCase().includes(query.trim().toLowerCase());
  };

  const visible = documents
    .filter(matchesQuery)
    .filter((d) => !onlyIncomplete || incomplete.includes(d));

  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageDocs = visible.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const isDocEncrypted = (doc) => {
    const meta = doc.metadata || {};
    return meta.is_encrypted === 'true' || meta.is_encrypted === true;
  };

  const actionLabels = {
    encrypt: { title: 'encrypt paper', button: 'encrypt', icon: Lock },
    view: { title: 'view encrypted paper', button: 'decrypt & view', icon: Eye },
    remove: { title: 'remove encryption', button: 'remove encryption', icon: ShieldOff },
  };

  return (
    <div>
      {/* Four glass stat cards became one line of type, and that line has now
          moved onto the masthead rule as the folio. It was drawing a second
          horizontal rule directly under the first one to carry three numbers.
          Refresh goes with it, as a header action. */}
      <PageHeader
        className="fade-up stagger-1"
        folio={
          <>
            <span className="tally-item"><b>{stats.total || '—'}</b>papers</span>
            <span className="tally-item"><b>{stats.analyses || '—'}</b>Read</span>
            {stats.gaps > 0 && <span className="tally-item"><b>{stats.gaps}</b>gaps</span>}
            <span className="tally-item"><b>{stats.total_chunks || '—'}</b>chunks</span>
            {documents.filter(isDocEncrypted).length > 0 && (
              <span className="tally-item">
                <b>{documents.filter(isDocEncrypted).length}</b>encrypted
              </span>
            )}
          </>
        }
      >
        <button className="tally-action" onClick={loadDocuments}>
          <RefreshCw size={12} /> Refresh
        </button>
      </PageHeader>

      {/* What the other three screens are for. "LitGraph" and "Scribe" mean
          nothing to someone who has just installed this, and each page's own
          "i" cannot help -- you have to already be there. Saying it once, on
          the page every launch opens, is what lets the page titles go. */}
      <section className="library-tour fade-up stagger-2">
        <button className="library-tour-toggle" onClick={toggleTour} aria-expanded={tourOpen}>
          {tourOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          <span>What&apos;s here</span>
        </button>
        {tourOpen && (
          <ul className="library-tour-list">
            {OTHER_FEATURES.map(({ id, path, label, icon: Icon, summary }) => (
              <li key={id}>
                <button className="library-tour-item" onClick={() => navigate(path)}>
                  <Icon size={15} className="library-tour-icon" />
                  <span className="library-tour-label">{label}</span>
                  <span className="library-tour-summary">{summary}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {documents.length > 0 && (
        <div className="library-panels fade-up stagger-2">
          <section className="panel">
            <h4 className="panel-head">Models in use</h4>
            {benchModels === null ? (
              <p className="panel-empty">Could not read the model registry</p>
            ) : benchModels.length === 0 ? (
              <p className="panel-empty">No model is configured</p>
            ) : (
              <ul className="panel-list">
                {benchModels.map(({ task, label }) => (
                  <li key={task}>
                    <span className="panel-key">{TASK_LABELS[task] || task}</span>
                    <span className="panel-val">{label}</span>
                  </li>
                ))}
              </ul>
            )}
            {/* The first-run note says this once and never returns, and it
                lands people in Bench -- a screen they have no reason to open
                again. This is where they actually are. */}
            <p className="panel-note">
              Runs on this machine.{' '}
              <button className="link-button" onClick={() => navigate('/bench')}>
                Change in Bench
              </button>
            </p>
          </section>

          {incomplete.length > 0 && (
            <section className="panel">
              <h4 className="panel-head">Needs attention</h4>
              <ul className="panel-list">
                {incomplete.slice(0, 4).map((doc) => (
                  <li key={doc.doc_id}>
                    <span className="panel-key">{doc.metadata?.title || doc.filename}</span>
                    <span className="panel-val">
                      {!hasAuthors(doc) && !doc.metadata?.year ? 'no authors, no year'
                        : !hasAuthors(doc) ? 'no authors' : 'no year'}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="panel-note">
                {incomplete.length} of {documents.length}.{' '}
                <button className="link-button" onClick={() => setOnlyIncomplete((on) => !on)}>
                  {onlyIncomplete ? 'Show all' : 'Show only these'}
                </button>
              </p>
            </section>
          )}

          <section className="panel">
            <h4 className="panel-head">Being written</h4>
            {scribeProjects === null ? (
              <p className="panel-empty">Could not read Scribe projects</p>
            ) : scribeProjects.length === 0 ? (
              <p className="panel-empty">
                Nothing in progress.{' '}
                <button className="link-button" onClick={() => navigate('/write')}>
                  Start a paper
                </button>
              </p>
            ) : (
              <>
                <ul className="panel-list">
                  {scribeProjects.slice(0, 4).map((proj) => (
                    <li key={proj.project_id}>
                      <span className="panel-key">{proj.name || proj.project_id}</span>
                      <span className="panel-val">{proj.has_pdf ? 'pdf' : 'draft'}</span>
                    </li>
                  ))}
                </ul>
                {/* One link, not one per row. Scribe has no route parameter and
                    does not restore a project, so a click on "uxtest" would
                    open whatever Scribe opens by default -- which is worse than
                    a single honest door. Per-draft links want a /write/:id
                    route first. */}
                <p className="panel-note">
                  {scribeProjects.length} in progress.{' '}
                  <button className="link-button" onClick={() => navigate('/write')}>
                    Continue writing
                  </button>
                </p>
              </>
            )}
          </section>
        </div>
      )}

      {/* The upload zone stops being a five-rem dashed pit and becomes the
          first row of the list it feeds. */}
      <div className="fade-up stagger-3">
        <UploadPanel onUploadComplete={loadDocuments} />
      </div>

      {documents.length > 0 && (
        <div className="kb-bar fade-up stagger-4">
          <span className="kb-search">
            <Search size={13} className="kb-search-icon" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Filter ${documents.length} papers by title, author or filename`}
              aria-label="Filter papers"
            />
          </span>
          {onlyIncomplete && (
            <button className="link-button" onClick={() => setOnlyIncomplete(false)}>
              showing {visible.length} needing attention &mdash; show all
            </button>
          )}
        </div>
      )}

      {/* Ingestion returns before the analysis does. Without this the reader is
          told the paper is in, opens LitGraph, and finds nothing. */}
      {jobs.active && (
        <p className="kb-progress" role="status">
          <span className="spinner" />
          {jobs.label || 'Working through the queue'}
          {jobs.total > 1 && <em> · {jobs.done} of {jobs.total}</em>}
          {jobs.queued > 0 && <em> · {jobs.queued} queued</em>}
        </p>
      )}

      <div className="paper-list fade-up stagger-4">
        {loading ? (
          <div className="loading-overlay">
            <div className="spinner spinner-lg" />
            <span>Loading papers…</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <h3>Nothing read yet</h3>
            <p>
              Drop a PDF on the line above. ThinkStack reads it on this machine,
              and the page starts to take its colour.
            </p>
          </div>
        ) : visible.length === 0 ? (
          <div className="empty-state">
            <h3>No match</h3>
            <p>Nothing in {documents.length} papers matches &ldquo;{query.trim()}&rdquo;.</p>
          </div>
        ) : (
          pageDocs.map((doc) => (
            <div key={doc.doc_id}>
              {/* Columns, per §6: what it is, how much of it there is, what
                  state it is in, and when. Serif for the title because it is
                  read; mono for the rest because it is counted. */}
              <div className="doc-item" onClick={() => toggleExpand(doc.doc_id)} style={{ cursor: 'pointer' }}>
                {/* The inner span is what the leader dots need: the text has to
                    be its own box so the dotted rule can be a sibling that eats
                    whatever width the title does not. */}
                {renamingDoc === doc.doc_id ? (
                  // Click-through would collapse the row out from under the
                  // input the moment you tried to type in it.
                  <form
                    className="doc-rename"
                    onClick={(e) => e.stopPropagation()}
                    onSubmit={(e) => { e.preventDefault(); submitRename(doc.doc_id); }}
                  >
                    <input
                      autoFocus
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Escape') setRenamingDoc(null); }}
                      aria-label="Paper title"
                    />
                    <button type="submit" className="link-button">Save</button>
                    <button type="button" className="link-button"
                            onClick={() => setRenamingDoc(null)}>Cancel</button>
                  </form>
                ) : (
                  <span className="doc-title" title={doc.metadata?.title || doc.filename}>
                    <span className="doc-title-text">{doc.metadata?.title || doc.filename}</span>
                    {/* Extraction is ~93% right, so about one paper in fourteen
                        is filed under the wrong name -- and that name labels it
                        on the map too. This is the only place to correct it. */}
                    <button
                      className="doc-rename-btn"
                      title="Correct this title"
                      aria-label="Correct this title"
                      onClick={(e) => { e.stopPropagation(); startRename(doc); }}
                    >
                      <Pencil size={12} />
                    </button>
                  </span>
                )}
                {/* Was the chunk count -- a bare "1" that told the reader
                    nothing, being a detail of how we index the text. The
                    authors are what identifies a paper at a glance, and we
                    now extract them accurately enough to print. */}
                <span className="doc-authors">
                  {/[a-z]/i.test(doc.metadata?.authors || '')
                    ? doc.metadata.authors
                    : '—'}
                </span>
                <span className={`doc-state ${isDocEncrypted(doc) ? 'is-locked' : ''}`}>
                  {isDocEncrypted(doc) ? 'encrypted' : 'read'}
                </span>
                {/* metadata.year, not a timestamp: the API has never returned
                    one, so the old row fell through to new Date() and stamped
                    every paper in the library with today. */}
                <span className="doc-year">{doc.metadata?.year || '—'}</span>
                <div className="doc-actions">
                  {isDocEncrypted(doc) ? (
                    <>
                      <button
                        className="btn-icon btn-icon-accent"
                        onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'view'); }}
                        title="View decrypted text"
                      >
                        <Eye size={15} />
                      </button>
                      <button
                        className="btn-icon btn-icon-warning"
                        onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'remove'); }}
                        title="Remove encryption"
                      >
                        <ShieldOff size={15} />
                      </button>
                    </>
                  ) : (
                    <button
                      className="btn-icon btn-icon-accent"
                      onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'encrypt'); }}
                      title="Encrypt paper"
                    >
                      <ShieldCheck size={15} />
                    </button>
                  )}
                  <button
                    className="btn-icon btn-icon-danger"
                    onClick={(e) => { e.stopPropagation(); handleDelete(doc.doc_id); }}
                    title="Delete paper"
                  >
                    <Trash2 size={15} />
                  </button>
                  {expandedDoc === doc.doc_id ? (
                    <ChevronUp size={13} color="var(--text-muted)" />
                  ) : (
                    <ChevronDown size={13} color="var(--text-muted)" />
                  )}
                </div>
              </div>
              {/* The opened paper: an indented extract, set in the reading
                  serif, hung off the row it belongs to. It was a nested card
                  on --bg-tertiary -- a box inside a box inside the page. */}
              {expandedDoc === doc.doc_id && docDetails[doc.doc_id] && (
                <div className="doc-extract">
                  {isDocEncrypted(doc) ? (
                    <p className="doc-extract-locked">
                      <Lock size={14} />
                      <span>This paper is encrypted. Use the view button to read it.</span>
                    </p>
                  ) : (
                    <p>
                      {docDetails[doc.doc_id].full_text?.substring(0, 800)}
                      {docDetails[doc.doc_id].full_text?.length > 800 && '…'}
                    </p>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {/* One batch at a time, a mark at each end. The shelf is meant to be
            read at a glance; a list long enough to scroll buries the folio. */}
        {visible.length > PAGE_SIZE && (
          <div className="kb-pager">
            <button
              className="kb-pager-btn"
              onClick={() => setPage((n) => Math.max(0, n - 1))}
              disabled={safePage === 0}
              aria-label="Previous papers"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="kb-pager-label">
              {safePage * PAGE_SIZE + 1}&ndash;
              {Math.min((safePage + 1) * PAGE_SIZE, visible.length)} of {visible.length}
            </span>
            <button
              className="kb-pager-btn"
              onClick={() => setPage((n) => Math.min(pageCount - 1, n + 1))}
              disabled={safePage >= pageCount - 1}
              aria-label="Next papers"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>

      {/* ── Encryption dialog ──
          Was a hand-built overlay: `.modal-overlay` (a class with no rule
          anywhere) plus eleven inline style objects, and none of the behaviour
          -- no Escape, no focus handling, and `onClick` on the backdrop, so a
          drag that started on the password field and finished outside the box
          closed the dialog and threw the typing away. It is the shared
          ConfirmDialog now, which is what that component's own docstring said
          it was for. */}
      {encryptingDoc && encryptAction && (
        <ConfirmDialog
          title={actionLabels[encryptAction]?.title}
          icon={actionLabels[encryptAction]?.icon || Lock}
          wide={Boolean(decryptedText)}
          onCancel={closeEncryptDialog}
        >
          {decryptedText ? (
            <>
              <div className="encrypt-read">
                <p>
                  {decryptedText.substring(0, 3000)}
                  {decryptedText.length > 3000 && '…'}
                </p>
              </div>
              <div className="confirm-actions">
                <button className="btn btn-secondary" onClick={closeEncryptDialog}>Close</button>
              </div>
            </>
          ) : (
            <form onSubmit={handleEncryptSubmit}>
              <div className="encrypt-field">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="input"
                  placeholder="Enter password…"
                  value={encryptPassword}
                  onChange={(e) => setEncryptPassword(e.target.value)}
                  autoFocus
                />
                <button
                  type="button"
                  className="btn-icon btn-icon-accent"
                  onClick={() => setShowPassword((v) => !v)}
                  title={showPassword ? 'hide password' : 'show password'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>

              {encryptError && <div className="encrypt-error">{encryptError}</div>}

              <div className="confirm-actions">
                <button type="button" className="btn btn-secondary" onClick={closeEncryptDialog}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className={`btn ${encryptAction === 'remove' ? 'btn-danger' : 'btn-primary'}`}
                  disabled={encryptBusy}
                >
                  {encryptBusy
                    ? <div className="spinner" />
                    : actionLabels[encryptAction]?.button}
                </button>
              </div>
            </form>
          )}
        </ConfirmDialog>
      )}
    </div>
  );
}
