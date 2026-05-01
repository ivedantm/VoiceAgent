import './GradeToggle.css';

export default function GradeToggle({ grade = 1, onChange }) {
  return (
    <div className="grade-toggle" id="grade-toggle">
      <button
        className={`grade-toggle-btn ${grade === 1 ? 'grade-toggle-btn--active' : ''}`}
        onClick={() => onChange?.(1)}
        id="grade-toggle-g1"
      >
        <span className="grade-toggle-number">1</span>
        <span className="grade-toggle-label">Uncontracted</span>
      </button>
      <button
        className={`grade-toggle-btn ${grade === 2 ? 'grade-toggle-btn--active' : ''}`}
        onClick={() => onChange?.(2)}
        id="grade-toggle-g2"
      >
        <span className="grade-toggle-number">2</span>
        <span className="grade-toggle-label">Contracted</span>
      </button>
    </div>
  );
}
