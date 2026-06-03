export function GoalEditor() {
  return (
    <div data-testid="goal-editor" style={{ border: '1px solid #e5e7eb', borderRadius: 12, padding: '1rem', background: '#fff' }}>
      <div data-testid="goal-empty" style={{ color: '#4b5563' }}>
        No goals configured. Goals and investment policy will appear here once configured via the API.
      </div>
    </div>
  );
}
