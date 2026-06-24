import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FilePlus2, Save, Play, Download, Trash2, Sparkles, FileText, Loader2,
} from 'lucide-react';
import { papersApi } from '../utils/api';

/** insert AI-generated body just before \end{document} (else append). */
function insertLatex(src, gen) {
  if (!gen) return src;
  const marker = '\\end{document}';
  const i = src.lastIndexOf(marker);
  if (i === -1) return `${src}\n\n${gen}\n`;
  return `${src.slice(0, i)}\n${gen}\n\n${src.slice(i)}`;
}

/**
 * AI LaTeX paper writer — create projects, edit source, generate LaTeX
 * with the local SLM, compile to PDF, and preview/download. All offline.
 */
export default function PaperWriter() {
  const [projects, setProjects] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [source, setSource] = useState('');
  const [dirty, setDirty] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const flash = (msg) => {
    setStatus(msg);
    setTimeout(() => setStatus(''), 2500);
  };

  const loadProjects = useCallback(async () => {
    try {
      const d = await papersApi.list();
      setProjects(d.projects || []);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const openProject = async (id) => {
    setError('');
    setStatus('');
    setPdfUrl(null);
    try {
      const d = await papersApi.get(id);
      setActiveId(id);
      setSource(d.source || '');
      setDirty(false);
      const proj = projects.find((p) => p.project_id === id);
      if (proj?.has_pdf) setPdfUrl(`${papersApi.downloadUrl(id)}?t=${Date.now()}`);
    } catch (e) {
      setError(e.message);
    }
  };

  const handleCreate = async () => {
    setCreating(true);
    setError('');
    try {
      const d = await papersApi.create((newName || 'untitled').trim());
      setNewName('');
      await loadProjects();
      setActiveId(d.project_id);
      setSource(d.source || '');
      setDirty(false);
      setPdfUrl(null);
    } catch (e) {
      setError(e.message);
    }
    setCreating(false);
  };

  const handleSave = async () => {
    if (!activeId) return;
    setBusy(true);
    setError('');
    try {
      await papersApi.save(activeId, source);
      setDirty(false);
      flash('saved');
    } catch (e) {
      setError(e.message);
    }
    setBusy(false);
  };

  const handleCompile = async () => {
    if (!activeId) return;
    setBusy(true);
    setError('');
    setStatus('compiling…');
    try {
      await papersApi.save(activeId, source);
      setDirty(false);
      await papersApi.compile(activeId);
      setPdfUrl(`${papersApi.downloadUrl(activeId)}?t=${Date.now()}`);
      flash('compiled');
      loadProjects();
    } catch (e) {
      setError(e.message);
      setStatus('');
    }
    setBusy(false);
  };

  const handleGenerate = async () => {
    if (!activeId || !prompt.trim()) return;
    setGenerating(true);
    setError('');
    try {
      const d = await papersApi.generate(activeId, prompt.trim(), source);
      setSource((prev) => insertLatex(prev, d.generated_latex || ''));
      setDirty(true);
      setPrompt('');
      flash('AI draft inserted');
    } catch (e) {
      setError(e.message);
    }
    setGenerating(false);
  };

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    try {
      await papersApi.remove(id);
      if (id === activeId) {
        setActiveId(null);
        setSource('');
        setPdfUrl(null);
      }
      loadProjects();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-header-left">
          <h2>Paper Writer</h2>
          <p>Draft, AI-generate, and compile LaTeX papers — fully offline.</p>
        </div>
      </div>

      {/* project bar */}
      <div className="card pw-bar">
        <div className="pw-projects">
          {projects.map((p) => (
            <button
              key={p.project_id}
              className={`pw-chip ${p.project_id === activeId ? 'active' : ''}`}
              onClick={() => openProject(p.project_id)}
              title={p.project_id}
            >
              <FileText size={14} />
              <span>{p.name || 'untitled'}</span>
              {p.has_pdf && <span className="pw-chip-dot" title="compiled" />}
              <span className="pw-chip-del" onClick={(e) => handleDelete(p.project_id, e)} title="delete">
                <Trash2 size={13} />
              </span>
            </button>
          ))}
          {projects.length === 0 && <span className="pw-hint">no projects yet — create one →</span>}
        </div>
        <div className="pw-create">
          <input
            className="input"
            placeholder="new paper name…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <button className="btn btn-primary" onClick={handleCreate} disabled={creating}>
            {creating ? <Loader2 size={16} className="pw-spin" /> : <FilePlus2 size={16} />}
            <span>New</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="toast error" style={{ position: 'static', margin: '0 0 1rem', whiteSpace: 'pre-wrap' }}>
          {error}
        </div>
      )}

      {!activeId ? (
        <div className="empty-state">
          <FileText size={48} />
          <h3>No paper open</h3>
          <p>Create a new paper or pick one above to start writing.</p>
        </div>
      ) : (
        <div className="pw-grid">
          {/* editor */}
          <motion.div
            className="card pw-editor"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 240, damping: 28 }}
          >
            <div className="pw-toolbar">
              <span className="pw-toolbar-title">
                main.tex {dirty && <span className="pw-dot" title="unsaved" />}
              </span>
              <div className="pw-toolbar-actions">
                {status && <span className="pw-status">{status}</span>}
                <button className="btn btn-secondary btn-sm" onClick={handleSave} disabled={busy}>
                  <Save size={14} /> <span>Save</span>
                </button>
                <button className="btn btn-primary btn-sm" onClick={handleCompile} disabled={busy}>
                  {busy ? <Loader2 size={14} className="pw-spin" /> : <Play size={14} />}
                  <span>Compile</span>
                </button>
                {pdfUrl && (
                  <a className="btn btn-secondary btn-sm" href={pdfUrl} download>
                    <Download size={14} /> <span>PDF</span>
                  </a>
                )}
              </div>
            </div>

            <textarea
              className="pw-textarea"
              value={source}
              spellCheck={false}
              onChange={(e) => { setSource(e.target.value); setDirty(true); }}
              placeholder="\\documentclass{article} ..."
            />

            <div className="pw-ai">
              <Sparkles size={16} className="pw-ai-icon" />
              <input
                className="input"
                placeholder="Describe a section, equation, or table for the AI to write…"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !generating && handleGenerate()}
              />
              <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || !prompt.trim()}>
                {generating ? <Loader2 size={16} className="pw-spin" /> : <Sparkles size={16} />}
                <span>Generate</span>
              </button>
            </div>
          </motion.div>

          {/* preview */}
          <div className="card pw-preview">
            <AnimatePresence mode="wait">
              {pdfUrl ? (
                <motion.iframe
                  key={pdfUrl}
                  title="pdf preview"
                  src={pdfUrl}
                  className="pw-iframe"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.3 }}
                />
              ) : (
                <div className="pw-empty">
                  <FileText size={42} />
                  <p>Compile to preview the PDF here.</p>
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
}
