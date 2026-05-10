import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GoalEditor } from '../src/components/GoalEditor';

describe('GoalEditor', () => {
  it('renders the empty state when no goals API exists', () => {
    render(<GoalEditor />);
    expect(screen.getByTestId('goal-editor')).toBeInTheDocument();
    expect(screen.getByTestId('goal-empty')).toHaveTextContent(
      'No goals configured. Goals and investment policy will appear here once configured via the API.',
    );
  });
});
