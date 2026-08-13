import { useState, useEffect, useCallback, lazy, Suspense } from 'react';
import { Trash2, RefreshCw, ChevronDown, ChevronUp, Lock, ShieldCheck, ShieldOff, Eye, EyeOff } from 'lucide-react';
import { documentsApi, encryptionApi } from '../utils/api';
import UploadPanel from './UploadPanel';
import PageHeader from './PageHeader';
import ConfirmDialog from './ConfirmDialog';

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
export default function Library() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, total_chunks: 0 });
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
      setStats({ total: data.total, total_chunks: data.total_chunks });
    } catch (err) {
      console.error('failed to load documents:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

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
        title="Library"
        folio={
          <>
            <span className="tally-item"><b>{stats.total || '—'}</b>papers</span>
            <span className="tally-item"><b>{stats.total_chunks || '—'}</b>chunks</span>
            <span className="tally-item">
              <b>{documents.filter(isDocEncrypted).length || '—'}</b>encrypted
            </span>
          </>
        }
      >
        <button className="tally-action" onClick={loadDocuments}>
          <RefreshCw size={12} /> Refresh
        </button>
      </PageHeader>

      {documents.length > 0 && (
        <Suspense fallback={null}><LibraryChart documents={documents} /></Suspense>
      )}

      {/* The upload zone stops being a five-rem dashed pit and becomes the
          first row of the list it feeds. */}
      <div className="fade-up stagger-3">
        <UploadPanel onUploadComplete={loadDocuments} />
      </div>

      <div className="paper-list fade-up stagger-4">
        {loading ? (
          <div className="loading-overlay">
            <div className="spinner spinner-lg" />
            <span>loading papers...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="empty-state">
            <h3>Nothing read yet</h3>
            <p>
              Drop a PDF on the line above. ThinkStack reads it on this machine,
              and the page starts to take its colour.
            </p>
          </div>
        ) : (
          documents.map((doc) => (
            <div key={doc.doc_id}>
              {/* Columns, per §6: what it is, how much of it there is, what
                  state it is in, and when. Serif for the title because it is
                  read; mono for the rest because it is counted. */}
              <div className="doc-item" onClick={() => toggleExpand(doc.doc_id)} style={{ cursor: 'pointer' }}>
                {/* The inner span is what the leader dots need: the text has to
                    be its own box so the dotted rule can be a sibling that eats
                    whatever width the title does not. */}
                <span className="doc-title" title={doc.metadata?.title || doc.filename}>
                  <span className="doc-title-text">{doc.metadata?.title || doc.filename}</span>
                </span>
                <span className="doc-chunks">{doc.chunks ?? '—'}</span>
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
                        title="view decrypted text"
                      >
                        <Eye size={15} />
                      </button>
                      <button
                        className="btn-icon btn-icon-warning"
                        onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'remove'); }}
                        title="remove encryption"
                      >
                        <ShieldOff size={15} />
                      </button>
                    </>
                  ) : (
                    <button
                      className="btn-icon btn-icon-accent"
                      onClick={(e) => { e.stopPropagation(); openEncryptDialog(doc.doc_id, 'encrypt'); }}
                      title="encrypt paper"
                    >
                      <ShieldCheck size={15} />
                    </button>
                  )}
                  <button
                    className="btn-icon btn-icon-danger"
                    onClick={(e) => { e.stopPropagation(); handleDelete(doc.doc_id); }}
                    title="delete paper"
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
                  placeholder="enter password…"
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
