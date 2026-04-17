import { useEffect, useState } from 'react';
import { fetchAgents, normalizeDetail } from '../api';
import { agentSpecs, type AgentSpec, type FieldSpec } from '../agentSpecs';
import type { AgentInfo } from '../types';

export function AgentRunner() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState('');
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchAgents()
      .then((list) => {
        setAgents(list);
        const first = list[0]?.name ?? '';
        setSelectedAgent(first);
        initForm(first);
      })
      .catch(() => setError('Failed to load agents'))
      .finally(() => setLoading(false));
  }, []);

  const initForm = (agentName: string) => {
    const spec = agentSpecs.find((s) => s.name === agentName);
    if (!spec) { setFormValues({}); return; }
    const defaults: Record<string, string> = {};
    for (const field of spec.fields) {
      defaults[field.name] = field.defaultValue ?? '';
    }
    setFormValues(defaults);
  };

  const handleAgentChange = (name: string) => {
    setSelectedAgent(name);
    setResult(null);
    setError('');
    initForm(name);
  };

  const currentSpec: AgentSpec | undefined = agentSpecs.find((s) => s.name === selectedAgent);

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentSpec) return;

    // Build request body from form values
    const body: Record<string, unknown> = {};
    for (const field of currentSpec.fields) {
      const raw = formValues[field.name]?.trim() ?? '';
      if (!raw && field.required) {
        setResult(null);
        setError(`${field.label} is required.`);
        return;
      }
      if (!raw) continue;

      if (field.type === 'json') {
        try {
          body[field.name] = JSON.parse(raw);
        } catch {
          setResult(null);
          setError(`${field.label}: invalid JSON.`);
          return;
        }
      } else if (field.type === 'number') {
        const value = Number(raw);
        if (!Number.isFinite(value)) {
          setResult(null);
          setError(`${field.label} must be a valid finite number.`);
          return;
        }
        body[field.name] = value;
      } else {
        body[field.name] = raw;
      }
    }

    setError('');
    setResult(null);
    setRunning(true);
    try {
      const resp = await fetch(
        `${import.meta.env.VITE_API_URL ?? '/api'}${currentSpec.endpoint}`,
        { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) },
      );
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        const detail = (errBody as Record<string, unknown>).detail ?? resp.statusText;
        throw new Error(normalizeDetail(detail));
      }
      const data = await resp.json();
      setResult(data as Record<string, unknown>);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Agent execution failed');
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <p data-testid="agent-runner-loading" style={{ color: '#6b7280' }}>Loading agents…</p>;
  if (agents.length === 0 && error) return <p data-testid="agent-runner-error" style={{ color: '#ef4444' }}>{error}</p>;

  return (
    <div>
      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.75rem' }}>
        <select
          value={selectedAgent}
          onChange={(e) => handleAgentChange(e.target.value)}
          style={{ flex: 1, padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: 6 }}
          data-testid="agent-select"
        >
          {agents.map((a) => (
            <option key={a.name} value={a.name}>{a.name}</option>
          ))}
        </select>
      </div>

      {currentSpec && (
        <p style={{ fontSize: '0.85rem', color: '#6b7280', margin: '0 0 0.75rem' }}>
          {currentSpec.description}
        </p>
      )}

      {currentSpec ? (
        <form onSubmit={handleRun} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {currentSpec.fields.map((field) => (
            <AgentField
              key={field.name}
              field={field}
              value={formValues[field.name] ?? ''}
              onChange={(val) => setFormValues((prev) => ({ ...prev, [field.name]: val }))}
            />
          ))}
          <button
            type="submit"
            disabled={running}
            style={{
              padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: 'white',
              borderRadius: 6, border: 'none', cursor: running ? 'wait' : 'pointer', alignSelf: 'flex-start',
            }}
          >
            {running ? 'Running…' : 'Run Agent'}
          </button>
        </form>
      ) : (
        <p style={{ color: '#6b7280', fontSize: '0.85rem' }}>
          No spec available for this agent. Select a different agent.
        </p>
      )}

      {error && <p data-testid="agent-runner-error" style={{ color: '#ef4444', marginTop: '0.5rem' }}>{error}</p>}

      {result && (
        <div data-testid="agent-runner-result" style={{ marginTop: '1rem', padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
          {/* Content field — displayed as preformatted text */}
          {typeof result.content === 'string' && (
            <pre style={{ whiteSpace: 'pre-wrap', margin: '0 0 0.75rem', fontSize: '0.85rem', lineHeight: 1.5 }}>
              {result.content}
            </pre>
          )}

          {/* Structured fields from spec */}
          {currentSpec && currentSpec.responseFields.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <tbody>
                {currentSpec.responseFields.map((key) => (
                  result[key] != null && (
                    <tr key={key} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '0.25rem 0.5rem', fontWeight: 500, width: '30%' }}>{key}</td>
                      <td style={{ padding: '0.25rem 0.5rem' }}>
                        {typeof result[key] === 'object' ? JSON.stringify(result[key]) : String(result[key])}
                      </td>
                    </tr>
                  )
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function AgentField({ field, value, onChange }: { field: FieldSpec; value: string; onChange: (val: string) => void }) {
  const baseStyle = { padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: 6, width: '100%', boxSizing: 'border-box' as const };

  if (field.type === 'textarea') {
    return (
      <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>
          {field.label}{field.required && ' *'}
        </span>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          rows={3}
          style={{ ...baseStyle, resize: 'vertical' }}
        />
      </label>
    );
  }

  if (field.type === 'select') {
    return (
      <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{field.label}</span>
        <select value={value} onChange={(e) => onChange(e.target.value)} style={baseStyle}>
          {field.options?.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      </label>
    );
  }

  if (field.type === 'json') {
    return (
      <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>{field.label}</span>
        <textarea
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          rows={2}
          style={{ ...baseStyle, fontFamily: 'monospace', fontSize: '0.8rem', resize: 'vertical' }}
        />
      </label>
    );
  }

  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
      <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>
        {field.label}{field.required && ' *'}
      </span>
      <input
        type={field.type === 'number' ? 'number' : 'text'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={field.placeholder}
        style={baseStyle}
      />
    </label>
  );
}
