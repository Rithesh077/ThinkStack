import { useState, useEffect, useRef, useCallback } from "react";
import {
  FileText,
  Plus,
  Save,
  Play,
  Download,
  Trash2,
  Sparkles,
  ChevronLeft,
  X,
  AlertCircle,
  FolderOpen,
  Loader2,
} from "lucide-react";
import { EditorView, basicSetup } from "codemirror";
import { EditorState } from "@codemirror/state";
import { oneDark } from "@codemirror/theme-one-dark";
import { ViewUpdate } from "@codemirror/view";
import { papersApi } from "../api";

/**
 * paper writer component.
 *
 * provides a codemirror-based editor for writing .ths prompt files.
 * the user writes prompts/pseudocode directly in the editor, clicks
 * generate to have the ai transform it into compilable latex, then
 * clicks compile to produce a pdf.
 *
 * workflow:
 *   1. create/open a project
 *   2. write prompts in the .ths editor
 *   3. click generate → ai replaces content with latex in-place
 *   4. click compile → pdflatex produces a pdf
 *   5. download the pdf
 */
export default function PaperWriter() {
  // project management
  const [projects, setProjects] = useState<any[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);
  const [projectName, setProjectName] = useState("");

  // editor state
  const [source, setSource] = useState("");
  const [saved, setSaved] = useState(true);

  // action states
  const [compiling, setCompiling] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [compileError, setCompileError] = useState("");

  // ui state
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");

  // refs
  const editorContainerRef = useRef<HTMLDivElement>(null);
  const editorViewRef = useRef<EditorView | null>(null);
  const sourceRef = useRef(source);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const activeProjectRef = useRef(activeProject);

  // keep refs in sync
  useEffect(() => {
    sourceRef.current = source;
  }, [source]);
  useEffect(() => {
    activeProjectRef.current = activeProject;
  }, [activeProject]);

  // load projects on mount
  useEffect(() => {
    loadProjects();
  }, []);

  // create/destroy codemirror when entering/leaving editor view
  useEffect(() => {
    if (!activeProject || !editorContainerRef.current) {
      // destroy editor if we leave editor view
      if (editorViewRef.current) {
        editorViewRef.current.destroy();
        editorViewRef.current = null;
      }
      return;
    }

    // create editor
    const updateListener = EditorView.updateListener.of((update: ViewUpdate) => {
      if (update.docChanged) {
        const newDoc = update.state.doc.toString();
        sourceRef.current = newDoc;
        setSource(newDoc);
        setSaved(false);

        // auto-save after 2s of inactivity
        if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
        saveTimerRef.current = setTimeout(async () => {
          const pid = activeProjectRef.current;
          if (pid) {
            try {
              await papersApi.saveSource(pid, sourceRef.current);
              setSaved(true);
            } catch {
              // silent auto-save failure
            }
          }
        }, 2000);
      }
    });

    const state = EditorState.create({
      doc: source,
      extensions: [
        basicSetup,
        oneDark,
        updateListener,
        EditorView.lineWrapping,
        EditorView.theme({
          "&": {
            height: "100%",
            fontSize: "14px",
          },
          ".cm-scroller": {
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
            overflow: "auto",
          },
          ".cm-content": {
            padding: "16px 0",
          },
          ".cm-gutters": {
            backgroundColor: "#0d0e14",
            borderRight: "1px solid rgba(255,255,255,0.06)",
          },
        }),
      ],
    });

    const view = new EditorView({
      state,
      parent: editorContainerRef.current,
    });

    editorViewRef.current = view;

    return () => {
      view.destroy();
      editorViewRef.current = null;
    };
    // only re-create on project switch, not on source changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeProject]);

  const loadProjects = async () => {
    try {
      const data = await papersApi.listProjects();
      setProjects(data.projects || []);
    } catch (e: any) {
      setError(`failed to load projects: ${e.message}`);
    }
  };

  const openProject = async (projectId: string) => {
    try {
      setError("");
      setCompileError("");
      const data = await papersApi.getProject(projectId);
      const proj = projects.find((p: any) => p.project_id === projectId);
      setProjectName(proj?.name || "untitled");
      setSource(data.source);
      setSaved(true);
      setPdfUrl(null);
      setActiveProject(projectId);
      if (proj?.has_pdf) {
        setPdfUrl(papersApi.downloadUrl(projectId));
      }
    } catch (e: any) {
      setError(`failed to open project: ${e.message}`);
    }
  };

  const createProject = async () => {
    const name = newName.trim() || "untitled";
    try {
      const data = await papersApi.createProject(name);
      setCreating(false);
      setNewName("");
      await loadProjects();
      openProject(data.project_id);
    } catch (e: any) {
      setError(`failed to create project: ${e.message}`);
    }
  };

  const saveNow = async () => {
    if (!activeProject) return;
    try {
      await papersApi.saveSource(activeProject, sourceRef.current);
      setSaved(true);
    } catch (e: any) {
      setError(`save failed: ${e.message}`);
    }
  };

  const handleGenerate = async () => {
    if (!activeProject) return;
    setGenerating(true);
    setError("");

    // save current content first
    try {
      await papersApi.saveSource(activeProject, sourceRef.current);
      setSaved(true);
    } catch {
      // continue
    }

    try {
      const data = await papersApi.generateLatex(
        activeProject,
        sourceRef.current,
        "",
      );
      const latex = data.generated_latex;

      // replace editor content in-place
      if (editorViewRef.current) {
        const view = editorViewRef.current;
        view.dispatch({
          changes: {
            from: 0,
            to: view.state.doc.length,
            insert: latex,
          },
        });
      }

      setSource(latex);
      setSaved(false);
    } catch (e: any) {
      setError(`generation failed: ${e.message}`);
    } finally {
      setGenerating(false);
    }
  };

  const handleCompile = async () => {
    if (!activeProject) return;
    setCompiling(true);
    setCompileError("");
    setError("");

    // save first
    try {
      await papersApi.saveSource(activeProject, sourceRef.current);
      setSaved(true);
    } catch {
      // continue
    }

    try {
      const data = await papersApi.compile(activeProject);
      setPdfUrl(data.pdf_url);
    } catch (e: any) {
      setCompileError(e.message);
    } finally {
      setCompiling(false);
    }
  };

  const handleDelete = async (projectId: string) => {
    try {
      await papersApi.deleteProject(projectId);
      if (activeProject === projectId) {
        setActiveProject(null);
        setSource("");
        setPdfUrl(null);
      }
      loadProjects();
    } catch (e: any) {
      setError(`delete failed: ${e.message}`);
    }
  };

  const goBack = () => {
    setActiveProject(null);
    setSource("");
    setPdfUrl(null);
    setCompileError("");
    setError("");
    loadProjects();
  };

  // ─── project list view ──────────────────────────────────────
  if (!activeProject) {
    return (
      <div className="pw">
        <div className="pw-header">
          <div className="pw-brand">
            <h1>thinkstack</h1>
            <span className="pw-subtitle">paper writer</span>
          </div>
        </div>

        {error && (
          <div className="pw-error">
            <AlertCircle size={16} />
            <span>{error}</span>
            <button className="pw-btn-icon" onClick={() => setError("")}>
              <X size={14} />
            </button>
          </div>
        )}

        <div className="pw-toolbar">
          {creating ? (
            <div className="pw-create-row">
              <input
                className="pw-input"
                type="text"
                placeholder="paper title..."
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && createProject()}
                autoFocus
              />
              <button className="pw-btn pw-btn-accent" onClick={createProject}>
                create
              </button>
              <button
                className="pw-btn pw-btn-ghost"
                onClick={() => {
                  setCreating(false);
                  setNewName("");
                }}
              >
                cancel
              </button>
            </div>
          ) : (
            <button
              className="pw-btn pw-btn-accent"
              onClick={() => setCreating(true)}
            >
              <Plus size={16} />
              new paper
            </button>
          )}
        </div>

        {projects.length === 0 ? (
          <div className="pw-empty">
            <FolderOpen size={48} strokeWidth={1} />
            <h3>no papers yet</h3>
            <p>
              create a new paper to start writing with ai-assisted latex
              generation
            </p>
          </div>
        ) : (
          <div className="pw-project-list">
            {projects.map((proj: any) => (
              <div
                key={proj.project_id}
                className="pw-project-card"
                onClick={() => openProject(proj.project_id)}
              >
                <div className="pw-project-icon">
                  <FileText size={20} />
                </div>
                <div className="pw-project-info">
                  <div className="pw-project-name">{proj.name}</div>
                  <div className="pw-project-meta">
                    {proj.has_pdf ? (
                      <span className="pw-badge pw-badge-ok">pdf ready</span>
                    ) : (
                      <span className="pw-badge pw-badge-draft">draft</span>
                    )}
                    <span className="pw-file-ext">.ths</span>
                  </div>
                </div>
                <button
                  className="pw-btn-icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(proj.project_id);
                  }}
                  title="delete"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ─── editor view ────────────────────────────────────────────
  return (
    <div className="pw pw-editor-mode">
      {/* toolbar */}
      <div className="pw-editor-toolbar">
        <div className="pw-toolbar-left">
          <button className="pw-btn pw-btn-ghost" onClick={goBack}>
            <ChevronLeft size={16} />
            projects
          </button>
          <span className="pw-filename">
            {projectName}.ths
          </span>
          <span className={`pw-save-dot ${saved ? "saved" : "unsaved"}`}>
            {saved ? "saved" : "unsaved"}
          </span>
        </div>

        <div className="pw-toolbar-right">
          <button
            className="pw-btn pw-btn-ghost"
            onClick={saveNow}
            disabled={saved}
          >
            <Save size={14} />
            save
          </button>

          <button
            className="pw-btn pw-btn-generate"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? (
              <Loader2 size={14} className="pw-spin" />
            ) : (
              <Sparkles size={14} />
            )}
            {generating ? "generating..." : "generate latex"}
          </button>

          <button
            className="pw-btn pw-btn-accent"
            onClick={handleCompile}
            disabled={compiling}
          >
            {compiling ? (
              <Loader2 size={14} className="pw-spin" />
            ) : (
              <Play size={14} />
            )}
            {compiling ? "compiling..." : "compile pdf"}
          </button>

          {pdfUrl && (
            <a
              className="pw-btn pw-btn-download"
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Download size={14} />
              pdf
            </a>
          )}
        </div>
      </div>

      {/* errors */}
      {error && (
        <div className="pw-error">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button className="pw-btn-icon" onClick={() => setError("")}>
            <X size={14} />
          </button>
        </div>
      )}

      {compileError && (
        <div className="pw-compile-error">
          <div className="pw-compile-error-head">
            <AlertCircle size={16} />
            <strong>compilation error</strong>
            <button
              className="pw-btn-icon"
              onClick={() => setCompileError("")}
            >
              <X size={14} />
            </button>
          </div>
          <pre className="pw-compile-log">{compileError}</pre>
        </div>
      )}

      {/* generating overlay */}
      {generating && (
        <div className="pw-gen-overlay">
          <Loader2 size={20} className="pw-spin" />
          <span>ai is generating latex from your prompts...</span>
        </div>
      )}

      {/* codemirror editor */}
      <div className="pw-editor-wrap" ref={editorContainerRef} />
    </div>
  );
}
