import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MacroDashboard } from '../src/components/MacroDashboard';

describe('MacroDashboard', () => {
  it('renders regime cards and overall metadata', () => {
    render(<MacroDashboard />);
    expect(screen.getByTestId('macro-dashboard')).toBeInTheDocument();
    expect(screen.getByTestId('regime-growth')).toHaveTextContent('expansion');
    expect(screen.getByTestId('regime-rates')).toHaveTextContent('rising');
    expect(screen.getByTestId('regime-inflation')).toHaveTextContent('moderate');
    expect(screen.getByTestId('macro-confidence')).toHaveTextContent('Overall confidence');
    expect(screen.getByTestId('macro-as-of')).toHaveTextContent('As of');
  });
});