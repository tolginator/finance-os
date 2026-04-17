import { useCallback, useRef, useState } from 'react';
import { agentSpecs } from '../agentSpecs';
import { normalizeDetail } from '../api';
import type { TaskDefinition, RunPipelineResponse } from '../types';

export function PipelineRunner() {
  const nextIdRef = useRef(1);
  const genTaskId = useCallback(() => `task-${nextIdRef.current++}`, []);

  const makeEmptyTask = useCallback((): TaskDefinition => {
    return { task_id: genTaskId(), agent_name: agentSpecs[0]?.name ?? '', prompt: '', kwargs: {}, depends_on: [] };
  }, [genTaskId]);

  const [tasks, setTasks] = useState<TaskDefinition[]>(() => [makeEmptyTask()]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunPipelineResponse | null>(null);
  const [error, setError] = useState('');

  const updateTask = (idx: number, patch: Partial<TaskDefinition>) => {
    setTasks((prev) => prev.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
  };

  const addTask = () => setTasks((prev) => [...prev, makeEmptyTask()]);

  const removeTask = (idx: number) => {
    const removedId = tasks[idx].task_id;
    setTasks((prev) =>
      prev
        .filter((_, i) => i !== idx)
        .map((t) => ({ ...t, depends_on: (t.depends_on ?? []).filter((id) => id !== removedId) })),
    );
  };

  const validate = (): string | null => {
    const ids = new Set<string>();
    for (const t of tasks) {
      if (!t.agent_name) return `Task ${t.task_id}: agent is required.`;
      if (ids.has(t.task_id!)) return `Duplicate task ID: ${t.task_id}`;
      ids.add(t.task_id!);
    }
    // Cycle detection — simple DFS
    const adj = new Map<string, string[]>();
    for (const t of tasks) adj.set(t.task_id!, t.depends_on ?? []);
    const visited = new Set<string>();
    const stack = new Set<string>();
    const hasCycle = (node: string): boolean => {
      if (stack.has(node)) return true;
      if (visited.has(node)) return false;
      visited.add(node);
      stack.add(node);
      for (const dep of adj.get(node) ?? []) { if (hasCycle(dep)) return true; }
      stack.delete(node);
      return false;
    };
    for (const id of adj.keys()) { if (hasCycle(id)) return 'Pipeline has a dependency cycle.'; }
    return null;
  };

  const handleRun = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) { setError(validationError); return; }

    setError('');
    setResult(null);
    setRunning(true);
    try {
      const resp = await fetch(`${import.meta.env.VITE_API_URL ?? '/api'}/pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tasks }),
      });
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        const detail = (errBody as Record<string, unknown>).detail ?? resp.statusText;
        throw new Error(normalizeDetail(detail));
      }
      setResult(await resp.json() as RunPipelineResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Pipeline failed');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleRun} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {tasks.map((task, idx) => (
          <TaskEditor
            key={task.task_id}
            task={task}
            allTaskIds={tasks.map((t) => t.task_id!)}
            onChange={(patch) => updateTask(idx, patch)}
            onRemove={tasks.length > 1 ? () => removeTask(idx) : undefined}
          />
        ))}

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" onClick={addTask} style={{ padding: '0.4rem 0.75rem', borderRadius: 6, border: '1px solid #d1d5db', background: 'white', cursor: 'pointer' }}>
            + Add Task
          </button>
          <button type="submit" disabled={running} style={{ padding: '0.4rem 0.75rem', borderRadius: 6, border: 'none', background: '#2563eb', color: 'white', cursor: running ? 'wait' : 'pointer' }}>
            {running ? 'Running…' : 'Run Pipeline'}
          </button>
        </div>
      </form>

      {error && <p data-testid="pipeline-error" style={{ color: '#ef4444', marginTop: '0.5rem' }}>{error}</p>}

      {result && (
        <div data-testid="pipeline-result" style={{ marginTop: '1rem', padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6 }}>
          <p style={{ margin: '0 0 0.5rem', fontWeight: 500 }}>
            Pipeline complete — {result.successful} succeeded, {result.failed} failed ({result.total_duration_ms}ms)
          </p>
          {result.results.map((r, i) => (
            <div key={i} style={{ padding: '0.5rem', marginBottom: '0.25rem', background: '#f9fafb', borderRadius: 4, fontSize: '0.85rem' }}>
              <strong>{(r as Record<string, unknown>).task_id as string ?? `Task ${i + 1}`}</strong>
              {' — '}
              <span style={{ color: (r as Record<string, unknown>).status === 'success' ? '#16a34a' : '#ef4444' }}>
                {String((r as Record<string, unknown>).status ?? 'unknown')}
              </span>
            </div>
          ))}
          {result.memo && (
            <pre style={{ marginTop: '0.5rem', fontSize: '0.8rem', whiteSpace: 'pre-wrap' }}>
              {JSON.stringify(result.memo, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

function TaskEditor({ task, allTaskIds, onChange, onRemove }: {
  task: TaskDefinition;
  allTaskIds: string[];
  onChange: (patch: Partial<TaskDefinition>) => void;
  onRemove?: () => void;
}) {
  const inputStyle = { padding: '0.4rem', border: '1px solid #d1d5db', borderRadius: 4, width: '100%', boxSizing: 'border-box' as const };

  return (
    <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: 6, background: '#fafafa' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <span style={{ fontWeight: 500, fontSize: '0.85rem' }}>{task.task_id}</span>
        {onRemove && (
          <button type="button" onClick={onRemove} aria-label={`Remove ${task.task_id}`} style={{ border: 'none', background: 'none', cursor: 'pointer', color: '#ef4444', fontSize: '0.9rem' }}>
            ✕
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', fontSize: '0.8rem' }}>
          Agent
          <select value={task.agent_name} onChange={(e) => onChange({ agent_name: e.target.value })} style={inputStyle}>
            {agentSpecs.map((s) => <option key={s.name} value={s.name}>{s.label}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', fontSize: '0.8rem' }}>
          Depends On
          <select multiple value={task.depends_on ?? []} onChange={(e) => onChange({ depends_on: Array.from(e.target.selectedOptions, (o) => o.value) })} style={{ ...inputStyle, minHeight: 40 }}>
            {allTaskIds.filter((id) => id !== task.task_id).map((id) => (
              <option key={id} value={id}>{id}</option>
            ))}
          </select>
        </label>
      </div>

      <label style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem', fontSize: '0.8rem' }}>
        Prompt
        <textarea value={task.prompt ?? ''} onChange={(e) => onChange({ prompt: e.target.value })} placeholder="Agent prompt…" rows={2} style={{ ...inputStyle, resize: 'vertical' }} />
      </label>
    </div>
  );
}
