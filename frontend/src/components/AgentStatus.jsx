import './AgentStatus.css';

const STATE_CONFIG = {
  idle:         { label: 'Idle',         color: 'var(--text-muted)',     dotClass: 'idle' },
  listening:    { label: 'Listening',    color: 'var(--color-success)',  dotClass: 'listening' },
  accumulating: { label: 'Accumulating', color: 'var(--color-info)',     dotClass: 'accumulating' },
  processing:   { label: 'Processing',  color: 'var(--color-warning)',  dotClass: 'processing' },
  confirming:   { label: 'Confirming',   color: 'var(--accent-400)',     dotClass: 'confirming' },
  correcting:   { label: 'Correcting',   color: 'var(--color-error)',    dotClass: 'correcting' },
};

export default function AgentStatus({ state = 'idle', className = '' }) {
  const config = STATE_CONFIG[state] || STATE_CONFIG.idle;

  return (
    <div className={`agent-status ${className}`} id="agent-status-indicator">
      <div className={`agent-status-dot agent-status-dot--${config.dotClass}`}>
        <span className="agent-status-dot-ring" />
      </div>
      <span className="agent-status-label" style={{ color: config.color }}>
        {config.label}
      </span>
    </div>
  );
}
