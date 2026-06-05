import { useState, useEffect, useCallback } from 'react';
import { FileText, Trash2, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import { documentsApi } from '../utils/api';
import UploadPanel from './UploadPanel';

/**
 * paper library component.
 *
 * displays all ingested documents, allows upload of new papers,
 * and provides document deletion. shows metadata and chunk
 * counts for each paper.
 */
export default function Library() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, total_chunks: 0 });
  const [expandedDoc, setExpandedDoc] = useState(null);
  const [docDetails, setDocDetails] = useState({});

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

  return (
    <div>
      <div className="page-header">
        <h2>paper library</h2>
        <p>manage your research paper collection</p>
      </div>

      <div className="stat-row">
        <div className="stat-card">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">papers ingested</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.total_chunks}</div>
          <div className="stat-label">knowledge chunks</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <span className="card-title">upload papers</span>
        </div>
        <UploadPanel onUploadComplete={loadDocuments} />
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">ingested papers</span>
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
        ) : (
          documents.map((doc) => (
            <div key={doc.doc_id}>
              <div className="doc-item" onClick={() => toggleExpand(doc.doc_id)} style={{ cursor: 'pointer' }}>
                <div className="doc-icon">
                  <FileText size={18} />
                </div>
                <div className="doc-info">
                  <div className="doc-title">
                    {doc.metadata?.title || doc.filename}
                  </div>
                  <div className="doc-meta">
                    {doc.metadata?.authors && `${doc.metadata.authors} | `}
                    {doc.metadata?.year && `${doc.metadata.year} | `}
                    {doc.chunks} chunks | {(doc.size_bytes / 1024).toFixed(0)} kb
                  </div>
                </div>
                <div className="doc-actions">
                  <button
                    className="btn-icon"
                    onClick={(e) => { e.stopPropagation(); handleDelete(doc.doc_id); }}
                    title="delete paper"
                  >
                    <Trash2 size={16} />
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
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.7' }}>
                      {docDetails[doc.doc_id].full_text?.substring(0, 800)}
                      {docDetails[doc.doc_id].full_text?.length > 800 && '...'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
