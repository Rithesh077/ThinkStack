import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import {
  BookOpen,
  Search,
  Brain,
  Target,
  Activity,
} from 'lucide-react';
import { systemApi } from './utils/api';
import Library from './components/Library';
import SearchPage from './components/Search';
import Analysis from './components/Analysis';
import GapAnalysis from './components/GapAnalysis';
import './index.css';

/**
 * main application shell with sidebar navigation and routing.
 *
 * provides the layout structure, navigation between views,
 * and displays local llm runtime status in the sidebar footer.
 */
export default function App() {
  const [llmStatus, setLlmStatus] = useState('checking');
  const [models, setModels] = useState([]);
  const [activeModel, setActiveModel] = useState('');
  const [switching, setSwitching] = useState(false);
  const [modelNote, setModelNote] = useState('');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await systemApi.health();
        setLlmStatus(data.llm?.status || data.ollama?.status || 'disconnected');
        const list = data.llm?.model_list || [];
        setModels(list);
        setActiveModel((prev) => prev || data.llm?.target_model || '');
      } catch {
        setLlmStatus('disconnected');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleModelChange = async (e) => {
    const model = e.target.value;
    if (!model || model === activeModel) return;
    const previous = activeModel;
    setActiveModel(model);
    setSwitching(true);
    setModelNote('');
    try {
      const res = await systemApi.setModel(model);
      if (res.restart_required) {
        setActiveModel(res.active_model || previous);
        setModelNote(`restart to apply ${prettyModel(model)}`);
      } else {
        setActiveModel(res.active_model || model);
      }
    } catch {
      setActiveModel(previous);
    }
    setSwitching(false);
  };

  const prettyModel = (name) =>
    name.replace(/\.gguf$/i, '').replace(/-Q4_K_M$/i, '');

  const navItems = [
    { to: '/', icon: BookOpen, label: 'Library' },
    { to: '/search', icon: Search, label: 'Search' },
    { to: '/analysis', icon: Brain, label: 'Analysis' },
    { to: '/gaps', icon: Target, label: 'Gap Finder' },
  ];

  return (
    <BrowserRouter>
      <div className="app-layout">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="brand-logo-container">
              <h1>Think<span className="brand-cursive">Stack</span></h1>
            </div>
          </div>

          <nav className="sidebar-nav">
            {navItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  `nav-link ${isActive ? 'active' : ''}`
                }
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>

          <div className="sidebar-footer">
            <div className="status-indicator">
              <div className={`status-dot ${llmStatus !== 'connected' ? 'disconnected' : ''}`} />
              <span>
                {switching ? 'Switching…' : llmStatus === 'connected' ? 'System Online' : `LLM: ${llmStatus}`}
              </span>
            </div>
          </div>
        </aside>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Library />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/analysis" element={<Analysis />} />
            <Route path="/gaps" element={<GapAnalysis />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
