import './StatsCard.css';

export default function StatsCard({ icon, label, value, subtext, accentColor }) {
  const color = accentColor || 'var(--accent-400)';

  return (
    <div className="stats-card glass-card" id={`stat-${label?.toLowerCase().replace(/\s+/g, '-')}`}>
      <div className="stats-card-icon" style={{ color, background: `${color}15` }}>
        {icon}
      </div>
      <div className="stats-card-content">
        <span className="stats-card-value" style={{ color }}>{value}</span>
        <span className="stats-card-label">{label}</span>
        {subtext && <span className="stats-card-subtext">{subtext}</span>}
      </div>
    </div>
  );
}
