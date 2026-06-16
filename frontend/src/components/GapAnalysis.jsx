import { useState, useEffect } from 'react';
import { Target, Compass, FileText, AlertTriangle, TrendingUp, MessageSquare } from 'lucide-react';
import { documentsApi, gapsApi } from '../utils/api';
import ChatDialog from './ChatDialog';

/**
 * research gap analysis component.
 *
 * orchestrates the full gap analysis pipeline across selected papers.
 * displays identified gaps with severity levels and actionable
 * research direction suggestions.
 * includes an AI chat dialog for interactive Q&A about gaps.
 */
export default function GapAnalysis() {
  const [documents, setDocuments] = useState([]);
  const [selectedDocs, setSelectedDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  // chat state
  const [chatMessages, setChatMessages] = useState([]);
  const [chatLoading, setChatLoading] = useState(false);

  useEffect(() => {
    const loadDocs = async () => {
      try {
        const data = await documentsApi.list();
        setDocuments(data.documents || []);
      } catch (err) {
        console.error('failed to load documents:', err);
      }
    };
    loadDocs();
  }, []);

  const toggleDoc = (docId) => {
    setSelectedDocs((prev) =>
      prev.includes(docId)
        ? prev.filter((id) => id !== docId)
        : [...prev, docId]
    );
  };

  const selectAll = () => {
    if (selectedDocs.length === documents.length) {
      setSelectedDocs([]);
    } else {
      setSelectedDocs(documents.map((d) => d.doc_id));
    }
  };

  const runGapAnalysis = async () => {
    if (selectedDocs.length < 2) return;

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const data = await gapsApi.analyze(selectedDocs);
      setResult(data);
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  };

  const handleChatSend = async (text) => {
    const userMsg = { role: 'user', content: text };
    setChatMessages((prev) => [...prev, userMsg]);
    setChatLoading(true);

    try {
      const docsToAnalyze = selectedDocs.length >= 2
        ? selectedDocs
        : documents.slice(0, 3).map(d => d.doc_id);

      const response = await gapsApi.analyze(docsToAnalyze);

      let reply = '';
      if (response.gaps?.length) {
        reply = `I found ${response.total_gaps} research gaps across ${response.papers_analyzed} papers. `;
        reply += `Top gap: "${response.gaps[0].description}" (${response.gaps[0].severity} severity). `;
      }
      if (response.suggestions?.length) {
        reply += `\n\nSuggested direction: "${response.suggestions[0].title}" — ${response.suggestions[0].description}`;
      }
      if (!reply) {
        reply = 'The gap analysis completed but found no significant gaps in the selected papers. Try selecting different or more papers.';
      }

      const assistantMsg = { role: 'assistant', content: reply };
      setChatMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${err.message}. Make sure the backend is running and at least 2 papers are uploaded.`,
      };
      setChatMessages((prev) => [...prev, errorMsg]);
    }
    setChatLoading(false);
  };

  const severityIcon = (severity) => {
    switch (severity) {
      case 'high': return <AlertTriangle size={14} color="var(--danger)" />;
      case 'medium': return <AlertTriangle size={14} color="var(--warning)" />;
      default: return <AlertTriangle size={14} color="var(--info)" />;
    }
  };

  const gapTypeLabel = (type) => {
    const labels = {
      contradictions: 'contradiction',
      under_explored: 'under-explored area',
      methodological: 'methodological gap',
      missing_validation: 'missing validation',
      temporal: 'temporal gap',
    };
    return labels[type] || type;
  };

  return (
    <div>
      <div className="page-header">
        <h2>research gap finder</h2>
        <p>identify gaps, contradictions, and promising research directions</p>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <span className="card-title">select papers for gap analysis (min. 2)</span>
          <button className="btn btn-secondary btn-sm" onClick={selectAll}>
            {selectedDocs.length === documents.length ? 'deselect all' : 'select all'}
          </button>
        </div>

        {documents.length === 0 ? (
          <div className="empty-state">
            <FileText size={36} />
            <h3>no papers available</h3>
            <p>upload at least 2 papers in the library first.</p>
          </div>
        ) : (
          <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
            {documents.map((doc) => (
              <div key={doc.doc_id} className="doc-item" onClick={() => toggleDoc(doc.doc_id)} style={{ cursor: 'pointer' }}>
                <label className="checkbox-wrap" onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedDocs.includes(doc.doc_id)}
                    onChange={() => toggleDoc(doc.doc_id)}
                  />
                </label>
                <div className="doc-info">
                  <div className="doc-title">{doc.metadata?.title || doc.filename}</div>
                  <div className="doc-meta">{doc.chunks} chunks</div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ marginTop: '1rem' }}>
          <button
            className="btn btn-primary"
            onClick={runGapAnalysis}
            disabled={loading || selectedDocs.length < 2}
          >
            {loading ? <div className="spinner" /> : <Target size={16} />}
            <span>{loading ? 'analyzing gaps...' : 'run gap analysis'}</span>
          </button>
          {selectedDocs.length < 2 && selectedDocs.length > 0 && (
            <span style={{ marginLeft: '0.75rem', fontSize: '0.8rem', color: 'var(--warning)' }}>
              select at least 2 papers
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="toast error" style={{ position: 'static', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {loading && (
        <div className="card">
          <div className="loading-overlay">
            <div className="spinner spinner-lg" />
            <span>running gap analysis pipeline...</span>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '400px', textAlign: 'center' }}>
              this may take a few minutes. the system is summarizing papers,
              extracting claims, and analyzing gaps using the local slm.
            </p>
          </div>
        </div>
      )}

      {result && (
        <>
          <div className="stat-row">
            <div className="stat-card">
              <div className="stat-value">{result.papers_analyzed}</div>
              <div className="stat-label">papers analyzed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{result.total_claims}</div>
              <div className="stat-label">claims extracted</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{result.total_gaps}</div>
              <div className="stat-label">gaps identified</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{result.total_suggestions}</div>
              <div className="stat-label">suggestions</div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div className="analysis-section">
              <h3><Target size={18} /> identified gaps</h3>
              {result.gaps && result.gaps.length > 0 ? (
                result.gaps.map((gap, i) => (
                  <div key={i} className={`gap-card severity-${gap.severity}`}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                      {severityIcon(gap.severity)}
                      <span className="gap-type" style={{ color: `var(--${gap.severity === 'high' ? 'danger' : gap.severity === 'medium' ? 'warning' : 'info'})` }}>
                        {gapTypeLabel(gap.gap_type)}
                      </span>
                      <span className={`badge badge-${gap.severity === 'high' ? 'danger' : gap.severity === 'medium' ? 'warning' : 'info'}`}>
                        {gap.severity}
                      </span>
                    </div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: '1.7' }}>
                      {gap.description}
                    </p>
                    {gap.evidence && gap.evidence.length > 0 && (
                      <div style={{ marginTop: '0.75rem' }}>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>evidence:</span>
                        <ul style={{ listStyle: 'none', padding: 0, marginTop: '0.25rem' }}>
                          {gap.evidence.map((ev, j) => (
                            <li key={j} style={{ fontSize: '0.8rem', color: 'var(--text-muted)', padding: '0.2rem 0', fontStyle: 'italic' }}>
                              - {ev}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <p style={{ color: 'var(--text-muted)' }}>no significant gaps identified.</p>
              )}
            </div>
          </div>

          <div className="card">
            <div className="analysis-section">
              <h3><Compass size={18} /> research direction suggestions</h3>
              {result.suggestions && result.suggestions.length > 0 ? (
                result.suggestions.map((sug, i) => (
                  <div key={i} className="suggestion-card">
                    <div className="suggestion-title">{sug.title}</div>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem', lineHeight: '1.7', marginBottom: '0.75rem' }}>
                      {sug.description}
                    </p>
                    {sug.rationale && (
                      <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
                        <strong>rationale:</strong> {sug.rationale}
                      </p>
                    )}
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <span className={`badge badge-${sug.feasibility === 'high' ? 'success' : sug.feasibility === 'medium' ? 'warning' : 'info'}`}>
                        feasibility: {sug.feasibility}
                      </span>
                      <span className={`badge badge-${sug.potential_impact === 'high' ? 'success' : sug.potential_impact === 'medium' ? 'warning' : 'info'}`}>
                        <TrendingUp size={10} />
                        impact: {sug.potential_impact}
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <p style={{ color: 'var(--text-muted)' }}>no suggestions generated.</p>
              )}
            </div>
          </div>
        </>
      )}

      {!result && !loading && (
        <div className="empty-state">
          <Target size={48} />
          <h3>find research gaps</h3>
          <p>
            select at least 2 papers above and run gap analysis.
            the system will identify contradictions, under-explored areas,
            and suggest promising research directions.
          </p>
        </div>
      )}

      <ChatDialog
        title="gap finder assistant"
        messages={chatMessages}
        onSend={handleChatSend}
        loading={chatLoading}
        placeholder="ask about research gaps and directions..."
      />
    </div>
  );
}
