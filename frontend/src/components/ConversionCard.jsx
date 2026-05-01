import './ConversionCard.css';

function formatDate(isoStr) {
  if (!isoStr) return '—';
  const d = new Date(isoStr);
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function confidenceBadge(val) {
  if (val >= 0.9) return 'badge-success';
  if (val >= 0.7) return 'badge-warning';
  return 'badge-error';
}

export default function ConversionCard({ conversion, index = 0 }) {
  const {
    raw_text,
    braille_output,
    braille_grade,
    stt_confidence,
    translate_confidence,
    created_at,
    confirmed,
  } = conversion;

  return (
    <div
      className="conversion-card glass-card fade-in"
      style={{ animationDelay: `${index * 60}ms` }}
      id={`conversion-card-${conversion.id || index}`}
    >
      <div className="conversion-card-header">
        <span className="badge badge-accent">
          Grade {braille_grade || 1}
        </span>
        <span className="text-sm text-muted">{formatDate(created_at)}</span>
      </div>

      <div className="conversion-card-body">
        <div className="conversion-card-text">
          <span className="conversion-card-text-label">Text</span>
          <p className="conversion-card-text-value">{raw_text}</p>
        </div>
        <div className="conversion-card-braille">
          <span className="conversion-card-text-label">Braille</span>
          <p className="conversion-card-braille-value font-mono">{braille_output}</p>
        </div>
      </div>

      <div className="conversion-card-footer">
        <div className="conversion-card-metrics">
          <span className={`badge ${confidenceBadge(stt_confidence || 0)}`}>
            STT {((stt_confidence || 0) * 100).toFixed(0)}%
          </span>
          <span className={`badge ${confidenceBadge(translate_confidence || 0)}`}>
            Trans {((translate_confidence || 0) * 100).toFixed(0)}%
          </span>
        </div>
        {confirmed !== undefined && (
          <span className={`badge ${confirmed ? 'badge-success' : 'badge-error'}`}>
            {confirmed ? '✓ Confirmed' : '✗ Rejected'}
          </span>
        )}
      </div>
    </div>
  );
}
