import { useState } from 'react';
import './BrailleDisplay.css';

export default function BrailleDisplay({ braille = '', originalText = '', label = 'Braille Output' }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!braille) return;
    try {
      await navigator.clipboard.writeText(braille);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard not available */
    }
  };

  return (
    <div className="braille-display glass-card" id="braille-display">
      <div className="braille-display-header">
        <span className="braille-display-label">{label}</span>
        {braille && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleCopy}
            id="copy-braille-btn"
          >
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--color-success)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Copied
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
                  <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
                </svg>
                Copy
              </>
            )}
          </button>
        )}
      </div>

      <div className={`braille-display-output ${braille ? 'braille-display-output--active' : ''}`}>
        {braille ? (
          <span className="braille-text">{braille}</span>
        ) : (
          <span className="braille-placeholder">
            ⠀⠀⠀ Braille output will appear here ⠀⠀⠀
          </span>
        )}
      </div>

      {originalText && (
        <div className="braille-display-original">
          <span className="text-sm text-muted">Original:</span>
          <span className="text-sm">{originalText}</span>
        </div>
      )}
    </div>
  );
}
