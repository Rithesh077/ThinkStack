import { useState, useCallback, useRef } from 'react';
import { CloudUpload, AlertCircle } from 'lucide-react';
import { documentsApi } from '../utils/api';
import { earn, EARNED_BY } from '../utils/pigments';

/**
 * document upload component with drag-and-drop support.
 *
 * handles pdf file selection via click or drag-and-drop,
 * shows upload progress, and reports results to the parent.
 */
export default function UploadPanel({ onUploadComplete }) {
  const [dragover, setDragover] = useState(false);
  // {done, total} while a run is in progress, null when idle. One object, so
  // "is it running" and "how far" can never disagree.
  const [run, setRun] = useState(null);
  const [failed, setFailed] = useState([]);
  // Set by Stop and read between files. Ingest is sequential and each file is
  // one request, so the honest thing to cancel is the QUEUE: the paper being
  // read finishes -- it is nearly done and the backend has already written
  // most of it -- and nothing after it starts.
  const cancelled = useRef(false);
  // The ref is what the loop reads between files; this is what the button
  // renders. A ref cannot be read during render, and the two serve different
  // consumers rather than one being a copy of the other.
  const [stopping, setStopping] = useState(false);

  const handleFiles = useCallback(async (files) => {
    const pdfFiles = Array.from(files).filter((f) => f.type === 'application/pdf');
    if (pdfFiles.length === 0) return;

    cancelled.current = false;
    setStopping(false);
    setFailed([]);
    setRun({ done: 0, total: pdfFiles.length });

    const problems = [];
    let ingested = 0;

    for (const [i, file] of pdfFiles.entries()) {
      if (cancelled.current) break;
      try {
        await documentsApi.upload(file);
        ingested += 1;
      } catch (err) {
        problems.push({ filename: file.name, error: err.message });
      }
      setRun({ done: i + 1, total: pdfFiles.length });
    }

    setFailed(problems);
    setRun(null);
    setStopping(false);

    // The first paper the machine actually reads earns the app its first
    // pigment. A failed upload earns nothing: the milestone is a paper in the
    // library, not an attempt at one.
    if (ingested > 0) earn(EARNED_BY.paperIngested);
    if (onUploadComplete) onUploadComplete();
  }, [onUploadComplete]);

  const stop = useCallback((e) => {
    e.stopPropagation();
    cancelled.current = true;
    setStopping(true);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragover(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handleFileInput = useCallback((e) => {
    handleFiles(e.target.files);
  }, [handleFiles]);

  const uploading = run !== null;

  return (
    <div>
      <div
        className={`upload-zone ${dragover ? 'dragover' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragover(true); }}
        onDragLeave={() => setDragover(false)}
        onDrop={handleDrop}
        onClick={() => { if (!uploading) document.getElementById('file-input').click(); }}
      >
        <input
          id="file-input"
          type="file"
          accept=".pdf"
          multiple
          onChange={handleFileInput}
          style={{ display: 'none' }}
        />
        {uploading ? (
          <>
            <div className="spinner" />
            <span className="upload-line">
              Reading {run.done + 1} of {run.total}…
            </span>
            {/* Dropping thirty papers by accident used to mean waiting for all
                thirty. The current file finishes -- it is nearly done and the
                backend has written most of it already -- and the queue stops
                there, so nothing is left half-ingested. */}
            <button type="button" className="upload-stop" onClick={stop}>
              {stopping ? 'Stopping…' : 'Stop'}
            </button>
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

      {/* No list of what worked: the shelf below names every paper, pages five
          at a time, and printing them again above it pushed the papers, the
          filter and the pager off the screen the paging exists to protect.
          A FAILURE still gets a line -- it is the only part that is not
          readable off the shelf. */}
      {failed.length > 0 && (
        <ul className="upload-failures">
          {failed.map((f) => (
            <li key={f.filename}>
              <AlertCircle size={14} />
              <span className="upload-failure-name">{f.filename}</span>
              <span className="upload-failure-why">{f.error}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
