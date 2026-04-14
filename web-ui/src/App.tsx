import { HealthStatus } from './components/HealthStatus';
import { AgentList } from './components/AgentList';
import { DigestPanel } from './components/DigestPanel';

export function App() {
  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '2rem 1rem', fontFamily: 'system-ui, sans-serif' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>finance-os</h1>
        <HealthStatus />
      </header>

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.125rem', marginBottom: '0.75rem' }}>Research Digest</h2>
        <DigestPanel />
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', marginBottom: '0.75rem' }}>Agents</h2>
        <AgentList />
      </section>
    </div>
  );
}
