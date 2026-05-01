import { useEffect, useState } from 'react';
import GradeToggle from '../components/GradeToggle';
import { api } from '../api/client';
import './Settings.css';

export default function Settings() {
  const [prefs, setPrefs] = useState({ braille_grade: 1, language: 'en', strip_fillers: true });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [prefsData, healthData] = await Promise.all([
          api.getPrefs(),
          api.health(),
        ]);
        if (prefsData.prefs && Object.keys(prefsData.prefs).length > 0) {
          setPrefs(prev => ({ ...prev, ...prefsData.prefs }));
        }
        setHealth(healthData);
      } catch (err) {
        console.error('Settings load error:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await api.updatePrefs(prefs);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      console.error('Save error:', err);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="settings page-enter" id="settings-page">
        <h1 className="settings-title">Settings</h1>
        <div className="settings-sections">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="glass-card" style={{ padding: 'var(--space-xl)' }}>
              <div className="skeleton" style={{ height: 20, width: '30%', marginBottom: 16 }} />
              <div className="skeleton" style={{ height: 44, width: '100%', marginBottom: 12 }} />
              <div className="skeleton" style={{ height: 14, width: '60%' }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="settings page-enter" id="settings-page">
      <div className="settings-header">
        <div>
          <h1 className="settings-title">Settings</h1>
          <p className="text-secondary text-sm">
            Configure your Braille translation preferences
          </p>
        </div>
        <button
          className={`btn ${saved ? 'btn-ghost' : 'btn-primary'}`}
          onClick={handleSave}
          disabled={saving}
          id="save-settings-btn"
          style={saved ? { borderColor: 'rgba(34,197,94,0.3)', color: 'var(--color-success)' } : {}}
        >
          {saving ? 'Saving...' : saved ? '✓ Saved' : 'Save Changes'}
        </button>
      </div>

      <div className="settings-sections">
        {/* Braille Grade */}
        <div className="settings-card glass-card">
          <h3 className="settings-card-title">Braille Grade</h3>
          <p className="text-sm text-secondary" style={{ marginBottom: 'var(--space-md)' }}>
            Grade 1 (uncontracted) spells out every letter. Grade 2 (contracted) uses abbreviations for common words.
          </p>
          <GradeToggle
            grade={prefs.braille_grade}
            onChange={(g) => setPrefs(prev => ({ ...prev, braille_grade: g }))}
          />
        </div>

        {/* Language */}
        <div className="settings-card glass-card">
          <h3 className="settings-card-title">Language</h3>
          <p className="text-sm text-secondary" style={{ marginBottom: 'var(--space-md)' }}>
            Primary language for speech recognition and Braille output.
          </p>
          <select
            className="input"
            value={prefs.language}
            onChange={(e) => setPrefs(prev => ({ ...prev, language: e.target.value }))}
            id="language-select"
            style={{ appearance: 'none', cursor: 'pointer', maxWidth: 300 }}
          >
            <option value="en">English (UEB)</option>
            <option value="es">Spanish</option>
            <option value="fr">French</option>
            <option value="de">German</option>
          </select>
        </div>

        {/* Normalizer */}
        <div className="settings-card glass-card">
          <h3 className="settings-card-title">Text Normalization</h3>
          <p className="text-sm text-secondary" style={{ marginBottom: 'var(--space-md)' }}>
            Automatically clean up speech-to-text output before Braille translation.
          </p>
          <label className="settings-toggle-row" id="strip-fillers-toggle">
            <div>
              <span className="settings-toggle-label">Strip filler words</span>
              <span className="text-sm text-muted" style={{ display: 'block', marginTop: 2 }}>
                Remove "umm", "uh", "like", etc. from transcripts
              </span>
            </div>
            <button
              className={`settings-switch ${prefs.strip_fillers ? 'settings-switch--on' : ''}`}
              onClick={() => setPrefs(prev => ({ ...prev, strip_fillers: !prev.strip_fillers }))}
              role="switch"
              aria-checked={prefs.strip_fillers}
            >
              <span className="settings-switch-thumb" />
            </button>
          </label>
        </div>

        {/* System Info */}
        <div className="settings-card glass-card">
          <h3 className="settings-card-title">System Status</h3>
          <div className="settings-info-grid">
            <div className="settings-info-row">
              <span className="text-sm text-muted">API Status</span>
              <span className={`badge ${health?.status === 'ok' ? 'badge-success' : 'badge-error'}`}>
                {health?.status === 'ok' ? '● Online' : '● Offline'}
              </span>
            </div>
            <div className="settings-info-row">
              <span className="text-sm text-muted">liblouis</span>
              <span className={`badge ${health?.translator_available ? 'badge-success' : 'badge-warning'}`}>
                {health?.translator_available ? '● Available' : '● Fallback Mode'}
              </span>
            </div>
            <div className="settings-info-row">
              <span className="text-sm text-muted">Version</span>
              <span className="text-sm font-mono text-secondary">1.0.0</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
