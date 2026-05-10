import { AgentList } from './components/AgentList';
import { DigestPanel } from './components/DigestPanel';
import { GoalEditor } from './components/GoalEditor';
import { HealthStatus } from './components/HealthStatus';
import { MacroDashboard } from './components/MacroDashboard';
import { PipelineRunner } from './components/PipelineRunner';
import { PortfolioView } from './components/PortfolioView';
import { StatsDashboard } from './components/StatsDashboard';

const sectionTitleStyle = { fontSize: '1.125rem', margin: '0 0 0.75rem' };

export function App() {
  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '2rem 1rem', fontFamily: 'system-ui, sans-serif' }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '2rem' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>finance-os</h1>
        <HealthStatus />
      </header>

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={sectionTitleStyle}>Portfolio</h2>
        <PortfolioView />
      </section>

      <section style={{ marginBottom: '2rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem', alignItems: 'start' }}>
        <div>
          <h2 style={sectionTitleStyle}>Macro Dashboard</h2>
          <MacroDashboard />
        </div>
        <div>
          <h2 style={sectionTitleStyle}>Goals</h2>
          <GoalEditor />
        </div>
      </section>

      <section style={{ marginBottom: '2rem' }}>
        <h2 style={sectionTitleStyle}>Research Digest</h2>
        <DigestPanel />
      </section>

      <section style={{ marginBottom: '2rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem', alignItems: 'start' }}>
        <div>
          <h2 style={sectionTitleStyle}>Pipeline Runner</h2>
          <PipelineRunner />
        </div>
        <div>
          <h2 style={sectionTitleStyle}>Stats Dashboard</h2>
          <StatsDashboard />
        </div>
      </section>

      <section>
        <h2 style={sectionTitleStyle}>Agent Catalog</h2>
        <AgentList />
      </section>
    </div>
  );
}
