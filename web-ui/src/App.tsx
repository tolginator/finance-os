import { HealthStatus } from './components/HealthStatus';
import { AgentList } from './components/AgentList';
import { AgentRunner } from './components/AgentRunner';
import { DigestPanel } from './components/DigestPanel';
import { KnowledgeGraphPanel } from './components/KnowledgeGraphPanel';
import { PipelineRunner } from './components/PipelineRunner';
import { StatsDashboard } from './components/StatsDashboard';

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

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.125rem', marginBottom: '0.75rem' }}>Knowledge Graph</h2>
        <KnowledgeGraphPanel />
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.125rem', marginBottom: '0.75rem' }}>Agent Runner</h2>
        <AgentRunner />
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.125rem', marginBottom: '0.75rem' }}>Research Pipeline</h2>
        <PipelineRunner />
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={{ fontSize: '1.125rem', marginBottom: '0.75rem' }}>Stats Dashboard</h2>
        <StatsDashboard />
      </section>

      <section>
        <h2 style={{ fontSize: '1.125rem', marginBottom: '0.75rem' }}>Agent Catalog</h2>
        <AgentList />
      </section>
    </div>
  );
}
