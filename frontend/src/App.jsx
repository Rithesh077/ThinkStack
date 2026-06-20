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
 * and displays ollama connection status in the sidebar footer.
 */
export default function App() {
  const [ollamaStatus, setOllamaStatus] = useState('checking');

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await systemApi.health();
        setOllamaStatus(data.ollama?.status || 'disconnected');
      } catch {
        setOllamaStatus('disconnected');
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const navItems = [
    { to: '/', icon: BookOpen, label: 'library' },
    { to: '/search', icon: Search, label: 'search' },
    { to: '/analysis', icon: Brain, label: 'analysis' },
    { to: '/gaps', icon: Target, label: 'gap finder' },
  ];

  return (
    <BrowserRouter>
      <div className="app-layout">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <h1>scholarlens</h1>
            <p>offline research agent</p>
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
              <div className={`status-dot ${ollamaStatus !== 'connected' ? 'disconnected' : ''}`} />
              <span>
                ollama: {ollamaStatus}
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
