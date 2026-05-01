import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import StatsCard from '../components/StatsCard';
import BrailleDisplay from '../components/BrailleDisplay';
import { api } from '../api/client';
import './Dashboard.css';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);
  const [demoText, setDemoText] = useState('');
  const [demoResult, setDemoResult] = useState(null);
  const [translating, setTranslating] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const [statsData, convData] = await Promise.all([
          api.getStats(),
          api.getConversions(5),
        ]);
        setStats(statsData);
        setRecent(convData.conversions || []);
      } catch (err) {
        console.error('Dashboard load error:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleDemo = async () => {
    if (!demoText.trim() || translating) return;
    setTranslating(true);
    try {
      const result = await api.translate(demoText);
      setDemoResult(result);
    } catch (err) {
      console.error('Translation error:', err);
    } finally {
      setTranslating(false);
    }
  };

  return (
    <div className="dashboard page-enter" id="dashboard-page">
      {/* Header */}
      <div className="dashboard-header">
        <div>
          <h1 className="dashboard-title">
            Welcome to <span className="text-accent">Sparky</span>
          </h1>
          <p className="text-secondary">
            Voice-activated Braille transcription agent
          </p>
        </div>
        <Link to="/live" className="btn btn-primary btn-lg" id="start-session-btn">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
          Start Live Session
        </Link>
      </div>

      {/* Stats Grid */}
      <div className="dashboard-stats">
        {loading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="stats-card glass-card">
              <div className="skeleton" style={{ width: 44, height: 44, borderRadius: 'var(--radius-md)' }} />
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div className="skeleton" style={{ height: 28, width: '60%' }} />
                <div className="skeleton" style={{ height: 14, width: '80%' }} />
              </div>
            </div>
          ))
        ) : (
          <>
            <StatsCard
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              }
              label="Total Conversions"
              value={stats?.total_conversions ?? 0}
              accentColor="var(--accent-400)"
            />
            <StatsCard
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              }
              label="Sessions"
              value={stats?.total_sessions ?? 0}
              accentColor="var(--color-info)"
            />
            <StatsCard
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              }
              label="STT Accuracy"
              value={`${((stats?.avg_stt_confidence ?? 0) * 100).toFixed(0)}%`}
              subtext="Average confidence"
              accentColor="var(--color-success)"
            />
            <StatsCard
              icon={
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="2" x2="22" y1="12" y2="12" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
              }
              label="Translation Acc."
              value={`${((stats?.avg_translate_confidence ?? 0) * 100).toFixed(0)}%`}
              subtext="Round-trip fidelity"
              accentColor="var(--color-warning)"
            />
          </>
        )}
      </div>

      {/* Quick Translate Demo */}
      <section className="dashboard-section">
        <h2 className="dashboard-section-title">Quick Translate</h2>
        <p className="text-secondary text-sm" style={{ marginBottom: 'var(--space-md)' }}>
          Type text below to see it converted to Braille instantly.
        </p>

        <div className="dashboard-translate-form">
          <textarea
            className="input"
            placeholder="Type something to translate to Braille..."
            value={demoText}
            onChange={(e) => setDemoText(e.target.value)}
            rows={3}
            id="demo-translate-input"
          />
          <button
            className="btn btn-primary"
            onClick={handleDemo}
            disabled={!demoText.trim() || translating}
            id="demo-translate-btn"
          >
            {translating ? 'Translating...' : 'Translate to Braille'}
          </button>
        </div>

        {demoResult && (
          <div className="dashboard-translate-result fade-in">
            <BrailleDisplay
              braille={demoResult.braille}
              originalText={demoResult.normalized}
              label="Translation Result"
            />
            <div className="dashboard-translate-meta">
              <span className="badge badge-accent">
                Confidence: {(demoResult.confidence * 100).toFixed(0)}%
              </span>
              {demoResult.used_fallback && (
                <span className="badge badge-warning">Fallback mode</span>
              )}
              {demoResult.normalizer_changes?.length > 0 && (
                <span className="badge badge-accent">
                  {demoResult.normalizer_changes.length} normalizations
                </span>
              )}
            </div>
          </div>
        )}
      </section>

      {/* Recent Activity */}
      <section className="dashboard-section">
        <div className="dashboard-section-header">
          <h2 className="dashboard-section-title">Recent Activity</h2>
          <Link to="/history" className="btn btn-ghost btn-sm" id="view-all-history-btn">
            View All →
          </Link>
        </div>

        {loading ? (
          <div className="dashboard-recent-list">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="dashboard-recent-item glass-card">
                <div className="skeleton" style={{ height: 16, width: '40%' }} />
                <div className="skeleton" style={{ height: 20, width: '70%', marginTop: 8 }} />
                <div className="skeleton" style={{ height: 14, width: '50%', marginTop: 8 }} />
              </div>
            ))}
          </div>
        ) : recent.length > 0 ? (
          <div className="dashboard-recent-list">
            {recent.map((c, i) => (
              <div key={c.id || i} className="dashboard-recent-item glass-card fade-in" style={{ animationDelay: `${i * 80}ms` }}>
                <div className="dashboard-recent-item-header">
                  <span className="badge badge-accent">Grade {c.braille_grade || 1}</span>
                  <span className="text-sm text-muted">
                    {c.created_at ? new Date(c.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : ''}
                  </span>
                </div>
                <p className="text-sm" style={{ marginTop: 4 }}>{c.raw_text}</p>
                <p className="font-mono text-accent" style={{ fontSize: '1rem', letterSpacing: '0.08em', marginTop: 4 }}>
                  {c.braille_output}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <h3>No conversions yet</h3>
            <p>Start a live session to begin translating speech to Braille.</p>
          </div>
        )}
      </section>
    </div>
  );
}
