import { useState, useEffect, useCallback, useRef, lazy, Suspense } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, CheckCircle, FileText, Trash2, RefreshCw, ChevronDown, ChevronUp, Lock, ShieldCheck, ShieldOff, Eye, EyeOff, BarChart2, Brain, Target, PenLine, Cpu, Search, Pencil, HardDrive, AlertTriangle } from 'lucide-react';
import { documentsApi, encryptionApi, papersApi, registryApi, useJobs } from '../utils/api';
import { FEATURES } from '../features';
import { libraryTourOpen, setLibraryTourOpen } from '../utils/firstRun';
import UploadPanel from './UploadPanel';

// Recharts is 300 kB and there is no chart to draw on an empty library, which
// is exactly the state a first run opens in. It arrives with the first paper.
const LibraryChart = lazy(() => import('./charts/LibraryChart'));

/**
 * Library - the paper collection.
 *
 * displays all ingested documents, allows upload of new papers,
 * and provides document deletion and encryption controls.
 * shows metadata, chunk counts, and encryption status for each paper.
 */
// Everything except Library itself: this list sits ON Library, and a page does
// not need to introduce itself. Read from FEATURES so a new feature appears
// here without anyone remembering to add it, and its wording cannot drift from
// the "i" guide that reads the same field.
const OTHER_FEATURES = FEATURES.filter((f) => f.id !== 'library');

// The routing table's task keys, in the words the rest of the app uses.
const TASK_LABELS = {
  general: 'General',
  analysis: 'Analysis',
  gap_analysis: 'Gap finding',
  latex_writer: 'LaTeX writing',
};

export default function Library() {
  const navigate = useNavigate();
  // Expanded only for someone who has never run this app -- see
  // libraryTourOpen(). Updating users have already found LitGraph and Scribe,
  // and introducing them to their own workspace reads as a regression.
  const [tourOpen, setTourOpen] = useState(libraryTourOpen);

  const toggleTour = () => {
    setTourOpen((open) => {
      setLibraryTourOpen(!open);
      return !open;
    });
  };

  const [query, setQuery] = useState('');
  const [onlyIncomplete, setOnlyIncomplete] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, total_chunks: 0, analyses: 0, gaps: 0 });

  // What the background queue is doing. Analysis is queued AFTER the upload
  // responds, so without this the user sees "ingested", opens LitGraph, finds
  // it empty, and has no way to know a model is still working.
  const jobs = useJobs();
  const wasBusy = useRef(false);

  // Overview panels. `null` means not loaded yet or the call failed -- which
  // the panels render differently, because "no papers" and "we could not ask"
  // are different facts and a dash for both hides an outage.
  const [scribeProjects, setScribeProjects] = useState(null);
  const [benchModels, setBenchModels] = useState(null);
  const [renamingDoc, setRenamingDoc] = useState(null);
  const [renameValue, setRenameValue] = useState('');
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
      // `routing`, not `models`. There is no "active model" -- the app routes
      // per task, and which entry serves a task depends on every other entry
      // (assignment, size against the memory free right now, rank). The
      // backend computes that and says so at routes_registry.py:186: doing it
      // again in javascript lets the two drift. Reading `models` and taking
      // the first ready one names a model that may serve nothing.
      // One row per TASK, not per model. Which model answers depends on the
      // task, and collapsing them hid the interesting case: a library with two
      // models installed routes Analysis to the bigger one and everything else
      // to the small one, and that is worth being able to see at a glance.
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

  // Refresh when the queue finishes, not while it runs. The counts only change
  // at the end of a job, and re-fetching every poll would reload the list under
  // the user's cursor twice a second. Same rule LitGraph uses.
  useEffect(() => {
    if (wasBusy.current && !jobs.active) loadDocuments();
    wasBusy.current = jobs.active;
  }, [jobs.active, loadDocuments]);

  const startRename = (doc) => {
    setRenamingDoc(doc.doc_id);
    setRenameValue(doc.metadata?.title || doc.filename || '');
  };

  const submitRename = async (docId) => {
    const title = renameValue.trim();
    if (!title) return;
    // Optimistic: the write touches every chunk of the paper and the list is
    // re-fetched anyway. Waiting to redraw makes a local edit feel remote.
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

  const isDocEncrypted = (doc) => {
    const meta = doc.metadata || {};
    return meta.is_encrypted === 'true' || meta.is_encrypted === true;
  };

  // Everything below is derived from the list already fetched -- no extra
  // call, and no counter that can disagree with the rows underneath it.
  const bytes = documents.reduce((n, d) => n + (d.size_bytes || 0), 0);
  const onDisk =
    bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB`
    : bytes >= 1e6 ? `${Math.round(bytes / 1e6)} MB`
    // Twenty small papers round to "0 MB", which reads as a broken counter
    // rather than as a small library.
    : `${Math.max(1, Math.round(bytes / 1e3))} KB`;
  const encrypted = documents.filter(isDocEncrypted).length;

  // A paper the extractor could not fully read. Worth surfacing because it is
  // FIXABLE now: the title is editable inline, and these are the rows where
  // the map label and any future citation would be wrong.
  const hasAuthors = (d) => /[a-z]/i.test(d.metadata?.authors || '');
  const incomplete = documents.filter((d) => !hasAuthors(d) || !d.metadata?.year);

  // Filter, not search. Semantic search over the text lives in LitGraph; what
  // a list of fifty papers needs is "where is the one I am thinking of", which
  // is a substring match over what the row already shows.
  const matchesQuery = (doc) => {
    if (!query.trim()) return true;
    const m = doc.metadata || {};
    return `${m.title || ''} ${m.authors || ''} ${doc.filename || ''}`
      .toLowerCase()
      .includes(query.trim().toLowerCase());
  };

  const visible = documents
    .filter(matchesQuery)
    .filter((d) => !onlyIncomplete || incomplete.includes(d));

  const actionLabels = {
    encrypt: { title: 'encrypt paper', button: 'encrypt', icon: Lock },
    view: { title: 'view encrypted paper', button: 'decrypt & view', icon: Eye },
    remove: { title: 'remove encryption', button: 'remove encryption', icon: ShieldOff },
  };

  return (
    <div>
      {/* What the other three screens are for.
          The nav says "LitGraph" and "Scribe", which mean nothing to someone
          who has just installed this. Each page's own "i" explains it, but you
          have to already be there -- and you will not open a screen whose name
          tells you nothing. Saying it once on the page everyone lands on is
          what lets the page titles go. */}
      <section className="library-tour fade-up stagger-2">
        <button
          className="library-tour-toggle"
          onClick={toggleTour}
          aria-expanded={tourOpen}
        >
          {tourOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          <span>What&apos;s here</span>
        </button>

        {tourOpen && (
          <ul className="library-tour-list">
            {OTHER_FEATURES.map(({ id, path, label, icon: Icon, summary }) => (
              <li key={id}>
                <button className="library-tour-item" onClick={() => navigate(path)}>
                  <Icon size={16} className="library-tour-icon" />
                  <span className="library-tour-label">{label}</span>
                  <span className="library-tour-summary">{summary}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* An empty library has nothing to report, and four cards reading "-"
          plus a chart with no data is what a new install used to open on. The
          one visit where the dashboard has least to say is the one where the
          user most needs telling what happens next. */}
      {!loading && documents.length === 0 ? (
        <section className="library-start fade-up stagger-2">
          <h2>Start by adding a paper.</h2>
          <p className="library-start-lede">
            Drop a PDF below. Everything after that happens on this machine —
            no account, no upload, no network.
          </p>
          <ol className="library-start-steps">
            <li>
              <span className="library-start-step">Read</span>
              title, authors and year are taken from the page layout, not guessed
            </li>
            <li>
              <span className="library-start-step">Split</span>
              the text becomes passages small enough to search precisely
            </li>
            <li>
              <span className="library-start-step">Embed</span>
              each passage gets a vector, so you can search by meaning
            </li>
            <li>
              <span className="library-start-step">Analyse</span>
              claims and gaps are extracted in the background — this one takes a
              minute, and the rest of the app stays usable
            </li>
          </ol>
          <p className="library-start-then">
            Then <button className="link-button" onClick={() => navigate('/litgraph')}>LitGraph</button> maps
            what you have, and <button className="link-button" onClick={() => navigate('/scribe')}>Scribe</button> cites
            it while you write.
          </p>
        </section>
      ) : (
      <div className="library-overview fade-up stagger-2">
        <div className="library-counts">
          <div className="stat-card">
            <div className="stat-card-top">
              <span className="stat-card-label">Papers Ingested</span>
              <FileText size={16} className="stat-card-icon" />
            </div>
            <div className="stat-value">{stats.total || '-'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-top">
              <span className="stat-card-label">Knowledge Chunks</span>
              <BarChart2 size={16} className="stat-card-icon" />
            </div>
            <div className="stat-value">{stats.total_chunks || '-'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-top">
              <span className="stat-card-label">Analyses Run</span>
              <Brain size={16} className="stat-card-icon" />
            </div>
            <div className="stat-value">{stats.analyses || '-'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-top">
              <span className="stat-card-label">Gaps Found</span>
              <Target size={16} className="stat-card-icon" />
            </div>
            <div className="stat-value">{stats.gaps || '-'}</div>
          </div>
          {/* Everything runs on this machine, so what it costs this machine is
              worth stating. Both are derived from the list already fetched. */}
          <div className="stat-card">
            <div className="stat-card-top">
              <span className="stat-card-label">Papers on Disk</span>
              <HardDrive size={16} className="stat-card-icon" />
            </div>
            <div className="stat-value">{documents.length ? onDisk : '-'}</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-top">
              <span className="stat-card-label">Encrypted</span>
              <ShieldCheck size={16} className="stat-card-icon" />
            </div>
            <div className="stat-value">{encrypted || '-'}</div>
          </div>
        </div>

        <div className="library-panels">
          <section className="stat-card panel">
            <div className="stat-card-top">
              <span className="stat-card-label">Models in Use</span>
              <Cpu size={16} className="stat-card-icon" />
            </div>
            {benchModels === null ? (
              <p className="panel-empty">could not read the model registry</p>
            ) : benchModels.length === 0 ? (
              <p className="panel-empty">no model is configured</p>
            ) : (
              <ul className="panel-list panel-list-scroll">
                {benchModels.map(({ task, label }) => (
                  <li key={task} className="panel-row">
                    <span className="panel-row-name">{TASK_LABELS[task] || task}</span>
                    <span className="panel-row-meta">{label}</span>
                  </li>
                ))}
              </ul>
            )}
            {/* The first-run banner says this once and never returns, and it
                lands people in Bench -- a screen they have no reason to open
                again. Library is where they actually are, so the fact that a
                model is running locally and can be swapped lives here too. */}
            <p className="panel-note">
              Runs on this machine. Nothing is uploaded.{' '}
              <button className="link-button" onClick={() => navigate('/bench')}>
                Change in Bench
              </button>
            </p>
          </section>

          {/* Not a statistic -- a worklist. Extraction is right about 93% of
              the time, so a few papers arrive without authors or a year, and
              those are exactly the rows whose LitGraph label is wrong and
              whose citation would be incomplete. Now that a title is editable
              inline, this is the only place that says WHICH ones to fix. */}
          {incomplete.length > 0 && (
            <section className="stat-card panel">
              <div className="stat-card-top">
                <span className="stat-card-label">Needs Attention</span>
                <AlertTriangle size={16} className="stat-card-icon" />
              </div>
              <ul className="panel-list panel-list-scroll">
                {incomplete.map((doc) => (
                  <li key={doc.doc_id} className="panel-row">
                    <span className="panel-row-name">
                      {doc.metadata?.title || doc.filename}
                    </span>
                    <span className="panel-row-meta">
                      {!hasAuthors(doc) && !doc.metadata?.year ? 'no authors, no year'
                        : !hasAuthors(doc) ? 'no authors' : 'no year'}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="panel-note">
                {incomplete.length} of {documents.length} papers.{' '}
                <button className="link-button"
                        onClick={() => setOnlyIncomplete((on) => !on)}>
                  {onlyIncomplete ? 'Show all papers' : 'Show only these'}
                </button>
              </p>
            </section>
          )}

          <section className="stat-card panel">
            <div className="stat-card-top">
              <span className="stat-card-label">Papers Being Written</span>
              <PenLine size={16} className="stat-card-icon" />
            </div>
            {scribeProjects === null ? (
              <p className="panel-empty">could not read Scribe projects</p>
            ) : scribeProjects.length === 0 ? (
              <p className="panel-empty">nothing in progress</p>
            ) : (
              <ul className="panel-list panel-list-scroll">
                {scribeProjects.map((proj) => (
                  <li key={proj.project_id} className="panel-row">
                    <PenLine size={12} className="panel-row-icon" />
                    <span className="panel-row-name">{proj.name || proj.project_id}</span>
                    {proj.has_pdf && <span className="badge badge-success">pdf</span>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
      )}

      {/* Upload comes before the knowledge base it fills -- the action, then
          what it produced. The chart is part of that section, not a preamble
          to it, so it sits under the heading rather than above the dropzone. */}
      <div className="fade-up stagger-3">
        <UploadPanel onUploadComplete={loadDocuments} />
      </div>

      <div className="kb-heading fade-up stagger-4">
        <h3 className="section-heading">Knowledge Base</h3>
        {documents.length > 0 && (
          <div className="kb-search">
            <Search size={14} className="kb-search-icon" />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={`Filter ${documents.length} papers by title, author or filename`}
              aria-label="Filter papers"
            />
          </div>
        )}
      </div>

      {documents.length > 0 && (
        <Suspense fallback={null}><LibraryChart documents={documents} /></Suspense>
      )}

      {/* The filter has to say it is on, and offer a way out. A list quietly
          showing three of twenty papers is indistinguishable from a bug. */}
      {onlyIncomplete && (
        <div className="kb-filter-note">
          <span>
            Showing {visible.length} paper{visible.length === 1 ? '' : 's'} missing
            an author list or a year. Click a title&apos;s pencil to correct it.
          </span>
          <button className="btn btn-secondary btn-sm"
                  onClick={() => setOnlyIncomplete(false)}>
            Show all
          </button>
        </div>
      )}

      {/* Ingestion returns before the analysis does. Without this the user is
          told "ingested", opens LitGraph, finds nothing, and concludes it is
          broken -- when a model is simply still working. */}
      {jobs.active && (
        <div className="kb-progress" role="status">
          <span className="spinner" />
          <span className="kb-progress-label">
            {jobs.label || 'Working through the queue'}
          </span>
          {jobs.total > 1 && (
            <span className="kb-progress-count">{jobs.done} of {jobs.total}</span>
          )}
          {jobs.queued > 0 && (
            <span className="kb-progress-count">{jobs.queued} queued</span>
          )}
        </div>
      )}

      <div className="card fade-up stagger-4">
        <div className="card-header">
          <span className="card-title"></span>
          <button className="btn btn-secondary btn-sm" onClick={loadDocuments}>
            <RefreshCw size={14} />
            <span>refresh</span>
          </button>
        </div>

        {loading ? (
          <div className="loading-overlay">
            <div className="spinner spinner-lg" />
            <span>loading papers...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <FileText size={48} />
            <h3>no papers yet</h3>
            <p>upload pdf research papers above to start building your knowledge base.</p>
          </div>
        ) : visible.length === 0 ? (
          <div className="empty-state">
            <Search size={48} />
            <h3>no match</h3>
            <p>nothing in {documents.length} papers matches &ldquo;{query.trim()}&rdquo;.</p>
          </div>
        ) : (
          visible.map((doc) => (
            <div key={doc.doc_id}>
              <div className="doc-item" onClick={() => toggleExpand(doc.doc_id)} style={{ cursor: 'pointer' }}>
                <div className="doc-icon">
                  {isDocEncrypted(doc) ? (
                    <Lock size={18} color="var(--accent-secondary)" />
                  ) : (
                    <CheckCircle size={18} color="var(--success)" />
                  )}
                </div>
                <div className="doc-info">
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
                      <button type="submit" className="btn btn-primary btn-sm">save</button>
                      <button type="button" className="btn btn-ghost btn-sm"
                              onClick={() => setRenamingDoc(null)}>cancel</button>
                    </form>
                  ) : (
                    <div className="doc-title">
                      {/* The extracted title, not the filename. "2402.02414.pdf"
                          tells a reader nothing, and the title is what labels
                          this paper everywhere else in the app. */}
                      {doc.metadata?.title || doc.filename}
                      <button
                        className="doc-rename-btn"
                        title="Correct this title"
                        aria-label="Correct this title"
                        onClick={(e) => { e.stopPropagation(); startRename(doc); }}
                      >
                        <Pencil size={12} />
                      </button>
                      {isDocEncrypted(doc) && (
                        <span className="badge badge-warning">encrypted</span>
                      )}
                    </div>
                  )}
                  <div className="doc-meta">
                    {/* Papers ingested before the layout fix have author
                        strings like ", ," -- joined separators with nothing
                        between them. Truthy, and meaningless to show. */}
                    {/[a-z]/i.test(doc.metadata?.authors || '') && (
                      <span>{doc.metadata.authors}</span>
                    )}
                    {doc.metadata?.year && <span>{doc.metadata.year}</span>}
                    <span><Clock size={12} /> {doc.filename}</span>
                  </div>
                </div>
                <div className="doc-actions" style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
                  {isDocEncrypted(doc) ? (
                    <>
                      <button
                        className="btn-icon btn-icon-accent"
                        onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'view'); }}
                        title="view decrypted text"
                      >
                        <Eye size={20} />
                      </button>
                      <button
                        className="btn-icon btn-icon-warning"
                        onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'remove'); }}
                        title="remove encryption"
                      >
                        <ShieldOff size={20} />
                      </button>
                    </>
                  ) : (
                    <button
                      className="btn-icon btn-icon-accent"
                      onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'encrypt'); }}
                      title="encrypt paper"
                    >
                      <ShieldCheck size={20} />
                    </button>
                  )}
                  <button
                    className="btn-icon btn-icon-danger"
                    onClick={(e) => { e.stopPropagation(); handleDelete(doc.doc_id); }}
                    title="delete paper"
                  >
                    <Trash2 size={20} />
                  </button>
                  {expandedDoc === doc.doc_id ? (
                    <ChevronUp size={16} color="var(--text-muted)" />
                  ) : (
                    <ChevronDown size={16} color="var(--text-muted)" />
                  )}
                </div>
              </div>
              {expandedDoc === doc.doc_id && docDetails[doc.doc_id] && (
                <div style={{ padding: '0 1.25rem 1rem', marginTop: '-0.25rem' }}>
                  <div className="card" style={{ background: 'var(--bg-tertiary)' }}>
                    {isDocEncrypted(doc) ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--warning)', fontSize: '0.85rem' }}>
                        <Lock size={14} />
                        <span>this document is encrypted. use the view button to read.</span>
                      </div>
                    ) : (
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.7' }}>
                        {docDetails[doc.doc_id].full_text?.substring(0, 800)}
                        {docDetails[doc.doc_id].full_text?.length > 800 && '...'}
                      </p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>

      {/* ── Encryption Modal ── */}
      {encryptingDoc && encryptAction && (
        <div
          className="modal-overlay"
          onClick={closeEncryptDialog}
          style={{
            position: 'fixed', inset: 0, zIndex: 1000,
            background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          <div
            className="card"
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%', maxWidth: '460px',
              padding: '1.5rem', animation: 'fadeIn 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
              {(() => { const Icon = actionLabels[encryptAction]?.icon || Lock; return <Icon size={20} />; })()}
              <h3 style={{ margin: 0 }}>{actionLabels[encryptAction]?.title}</h3>
            </div>

            {decryptedText ? (
              <div>
                <div className="card" style={{ background: 'var(--bg-tertiary)', maxHeight: '400px', overflowY: 'auto' }}>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.7', whiteSpace: 'pre-wrap' }}>
                    {decryptedText.substring(0, 3000)}
                    {decryptedText.length > 3000 && '...'}
                  </p>
                </div>
                <button
                  className="btn btn-secondary"
                  onClick={closeEncryptDialog}
                  style={{ marginTop: '1rem', width: '100%' }}
                >
                  close
                </button>
              </div>
            ) : (
              <form onSubmit={handleEncryptSubmit}>
                <div style={{ position: 'relative', marginBottom: '1rem' }}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    className="input"
                    placeholder="enter password…"
                    value={encryptPassword}
                    onChange={(e) => setEncryptPassword(e.target.value)}
                    autoFocus
                    style={{ width: '100%', paddingRight: '2.5rem' }}
                  />
                  <button
                    type="button"
                    className="btn-icon btn-icon-accent"
                    onClick={() => setShowPassword((v) => !v)}
                    style={{ position: 'absolute', right: '0.25rem', top: '50%', transform: 'translateY(-50%)' }}
                    title={showPassword ? 'hide password' : 'show password'}
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>

                {encryptError && (
                  <div style={{
                    color: 'var(--danger)', background: 'rgba(248,113,113,0.1)',
                    padding: '0.5rem 0.75rem', borderRadius: '0.5rem',
                    fontSize: '0.85rem', marginBottom: '1rem',
                  }}>
                    {encryptError}
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={closeEncryptDialog}
                    style={{ flex: 1 }}
                  >
                    cancel
                  </button>
                  <button
                    type="submit"
                    className={`btn ${encryptAction === 'remove' ? 'btn-danger' : 'btn-primary'}`}
                    disabled={encryptBusy}
                    style={{ flex: 1 }}
                  >
                    {encryptBusy ? (
                      <div className="spinner" style={{ width: '16px', height: '16px' }} />
                    ) : (
                      actionLabels[encryptAction]?.button
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
