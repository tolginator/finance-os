import { macroRegimeMock, type RegimeDimension } from '../mockData';

function confidenceWidth(confidence: string): number {
  switch (confidence.toLowerCase()) {
    case 'high':
      return 85;
    case 'moderate':
      return 60;
    case 'low':
      return 35;
    default:
      return 50;
  }
}

function trendArrow(trend: string): string {
  switch (trend.toLowerCase()) {
    case 'rising':
      return '↑';
    case 'falling':
      return '↓';
    default:
      return '→';
  }
}

function signalColor(value: string): string {
  switch (value.toLowerCase()) {
    case 'expansion':
    case 'falling':
    case 'low':
      return '#16a34a';
    case 'contraction':
    case 'rising':
    case 'high':
      return '#dc2626';
    default:
      return '#d97706';
  }
}

function confidenceColor(level: string): string {
  switch (level.toLowerCase()) {
    case 'high':
      return '#16a34a';
    case 'moderate':
      return '#d97706';
    case 'low':
      return '#dc2626';
    default:
      return '#6b7280';
  }
}

function RegimeCard({ label, dimension, testId }: { label: string; dimension: RegimeDimension; testId: string }) {
  return (
    <div
      data-testid={testId}
      style={{
        border: '1px solid #e5e7eb',
        borderRadius: 12,
        padding: '1rem',
        background: '#fff',
      }}
    >
      <div style={{ fontSize: '0.85rem', color: '#6b7280', marginBottom: '0.25rem' }}>{label}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <div style={{ fontSize: '1.1rem', fontWeight: 700, color: signalColor(dimension.regime) }}>{dimension.regime}</div>
        <div style={{ fontSize: '1rem', color: signalColor(dimension.trend) }}>
          {trendArrow(dimension.trend)} {dimension.trend}
        </div>
      </div>
      <div style={{ fontSize: '0.85rem', marginBottom: '0.35rem', color: '#4b5563' }}>Confidence: {dimension.confidence}</div>
      <div style={{ height: 10, borderRadius: 999, background: '#f3f4f6', overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${confidenceWidth(dimension.confidence)}%`,
            background: confidenceColor(dimension.confidence),
          }}
        />
      </div>
    </div>
  );
}

export function MacroDashboard() {
  return (
    <div data-testid="macro-dashboard" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
        <RegimeCard label="Growth" dimension={macroRegimeMock.growth} testId="regime-growth" />
        <RegimeCard label="Rates" dimension={macroRegimeMock.rates} testId="regime-rates" />
        <RegimeCard label="Inflation" dimension={macroRegimeMock.inflation} testId="regime-inflation" />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <div data-testid="macro-confidence" style={{ fontSize: '0.95rem' }}>
          Overall confidence: <strong style={{ color: confidenceColor(macroRegimeMock.overall_confidence) }}>{macroRegimeMock.overall_confidence}</strong>
        </div>
        <div data-testid="macro-as-of" style={{ fontSize: '0.9rem', color: '#6b7280' }}>
          As of {new Date(macroRegimeMock.as_of).toLocaleString()}
        </div>
      </div>
    </div>
  );
}