import { useEffect, useRef, useState } from 'react';
import './WaveformViz.css';

export default function WaveformViz({ isActive = false, barCount = 32 }) {
  const [bars, setBars] = useState(() =>
    Array.from({ length: barCount }, () => 0.1)
  );
  const rafRef = useRef(null);

  useEffect(() => {
    if (!isActive) {
      setBars(Array.from({ length: barCount }, () => 0.08));
      return;
    }

    let frame = 0;
    const animate = () => {
      frame++;
      setBars(prev =>
        prev.map((_, i) => {
          const phase = (i / barCount) * Math.PI * 2 + frame * 0.08;
          const base = 0.15 + Math.sin(phase) * 0.25 + Math.sin(phase * 2.3) * 0.15;
          const jitter = Math.random() * 0.2;
          return Math.min(1, Math.max(0.08, base + jitter));
        })
      );
      rafRef.current = requestAnimationFrame(animate);
    };

    rafRef.current = requestAnimationFrame(animate);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [isActive, barCount]);

  return (
    <div className={`waveform ${isActive ? 'waveform--active' : ''}`} id="waveform-viz">
      {bars.map((height, i) => (
        <div
          key={i}
          className="waveform-bar"
          style={{
            height: `${height * 100}%`,
            animationDelay: `${i * 30}ms`,
          }}
        />
      ))}
    </div>
  );
}
