import { useState, useCallback } from 'react';
import { CloudUpload, CheckCircle, AlertCircle } from 'lucide-react';
import { documentsApi } from '../utils/api';
import { earn, EARNED_BY } from '../utils/pigments';

/**
 * document upload component with drag-and-drop support.
 *
 * handles pdf file selection via click or drag-and-drop,
 * shows upload progress, and reports results to the parent.
 */
export default function UploadPanel({ onUploadComplete }) {
  const [uploading, setUploading] = useState(false);
  const [dragover, setDragover] = useState(false);
  const [results, setResults] = useState([]);

  const handleFiles = useCallback(async (files) => {
    const pdfFiles = Array.from(files).filter(
      (f) => f.type === 'application/pdf'
    );

    if (pdfFiles.length === 0) return;

    setUploading(true);
    const uploadResults = [];

    for (const file of pdfFiles) {
      try {
        const result = await documentsApi.upload(file);
        uploadResults.push({
          filename: file.name,
          status: 'success',
          ...result,
        });
      } catch (err) {
        uploadResults.push({
          filename: file.name,
          status: 'error',
          error: err.message,
        });
      }
    }

    setResults(uploadResults);
    setUploading(false);

    // The first paper the machine actually reads earns the app its first
    // pigment. A failed upload earns nothing: the milestone is a paper in the
    // library, not an attempt at one.
    if (uploadResults.some((r) => r.status === 'success' || r.status === 'ingested')) {
      earn(EARNED_BY.paperIngested);
    }

    if (onUploadComplete) {
      onUploadComplete(uploadResults);
    }
  }, [onUploadComplete]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragover(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handleFileInput = useCallback((e) => {
    handleFiles(e.target.files);
  }, [handleFiles]);

  return (
    <div>
      <div
        className={`upload-zone ${dragover ? 'dragover' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
        onDragLeave={() => setDragover(false)}
        onDrop={handleDrop}
        onClick={() => document.getElementById('file-input').click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".pdf"
          multiple
          onChange={handleFileInput}
          style={{ display: 'none' }}
        />
        {/* One row, not a pit. It sits at the head of the list it feeds, so
            adding a paper reads as writing the next line rather than as
            visiting a separate uploader. */}
        {uploading ? (
          <>
            <div className="spinner" />
            <span className="upload-line">Reading…</span>
          </>
        ) : (
          <>
            <CloudUpload size={15} strokeWidth={1.5} className="upload-mark" />
            <span className="upload-line">
              Drop PDFs here, or{' '}
              <button
                type="button"
                className="upload-browse-btn"
                onClick={(e) => { e.stopPropagation(); document.getElementById('file-input').click(); }}
              >
                browse
              </button>
            </span>
          </>
        )}
      </div>

      {results.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          {results.map((r, i) => (
            <div
              key={i}
              className="doc-item"
              style={{
                borderColor: (r.status === 'success' || r.status === 'ingested')
                  ? 'var(--rule)'
                  : 'var(--mark-rule)',
              }}
            >
              <div className="doc-icon">
                {r.status === 'success' || r.status === 'ingested' ? (
                  <CheckCircle size={18} color="var(--success)" />
                ) : (
                  <AlertCircle size={18} color="var(--danger)" />
                )}
              </div>
              <div className="doc-info">
                <div className="doc-title">{r.filename}</div>
                {(r.status !== 'success' && r.status !== 'ingested') && (
                  <div className="doc-meta">
                    {r.error}
                  </div>
                )}
              </div>
              <span className={`badge badge-${r.status === 'success' || r.status === 'ingested' ? 'success' : 'danger'}`}>
                {r.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
