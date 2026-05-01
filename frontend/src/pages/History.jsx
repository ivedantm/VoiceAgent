import { useEffect, useState } from 'react';
import ConversionCard from '../components/ConversionCard';
import { api } from '../api/client';
import './History.css';

export default function History() {
  const [conversions, setConversions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [limit, setLimit] = useState(20);
  const [search, setSearch] = useState('');

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await api.getConversions(limit);
        setConversions(data.conversions || []);
      } catch (err) {
        console.error('History load error:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [limit]);

  const filtered = search.trim()
    ? conversions.filter(
        (c) =>
          c.raw_text?.toLowerCase().includes(search.toLowerCase()) ||
          c.braille_output?.includes(search)
      )
    : conversions;

  return (
    <div className="history page-enter" id="history-page">
      <div className="history-header">
        <div>
          <h1 className="history-title">Conversion History</h1>
          <p className="text-secondary text-sm">
            Browse past speech → Braille translations
          </p>
        </div>
        <span className="badge badge-accent">
          {conversions.length} conversion{conversions.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Search & Controls */}
      <div className="history-controls">
        <div className="history-search">
          <svg className="history-search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <input
            className="input"
            placeholder="Search conversions..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            id="history-search-input"
          />
        </div>
        <select
          className="input history-limit-select"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          id="history-limit-select"
        >
          <option value={10}>Last 10</option>
          <option value={20}>Last 20</option>
          <option value={50}>Last 50</option>
          <option value={100}>Last 100</option>
        </select>
      </div>

      {/* Results */}
      {loading ? (
        <div className="history-list">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="glass-card" style={{ padding: 'var(--space-lg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                <div className="skeleton" style={{ height: 20, width: '15%' }} />
                <div className="skeleton" style={{ height: 14, width: '20%' }} />
              </div>
              <div className="skeleton" style={{ height: 16, width: '65%', marginBottom: 8 }} />
              <div className="skeleton" style={{ height: 20, width: '80%', marginBottom: 12 }} />
              <div style={{ display: 'flex', gap: 8 }}>
                <div className="skeleton" style={{ height: 22, width: 60 }} />
                <div className="skeleton" style={{ height: 22, width: 70 }} />
              </div>
            </div>
          ))}
        </div>
      ) : filtered.length > 0 ? (
        <div className="history-list">
          {filtered.map((c, i) => (
            <ConversionCard key={c.id || i} conversion={c} index={i} />
          ))}
        </div>
      ) : (
        <div className="empty-state" style={{ marginTop: 'var(--space-2xl)' }}>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
          <h3>{search ? 'No matching conversions' : 'No conversions yet'}</h3>
          <p>
            {search
              ? 'Try adjusting your search query.'
              : 'Start a live session to create your first conversion.'}
          </p>
        </div>
      )}
    </div>
  );
}
