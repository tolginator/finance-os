import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GoalEditor } from '../src/components/GoalEditor';

describe('GoalEditor', () => {
  it('renders goals and policy table', () => {
    render(<GoalEditor />);
    expect(screen.getByTestId('goal-editor')).toBeInTheDocument();
    expect(screen.getByTestId('goal-list')).toBeInTheDocument();
    expect(screen.getByTestId('goal-retirement-primary')).toBeInTheDocument();
    expect(screen.getByTestId('goal-wealth-building-secondary')).toBeInTheDocument();
    expect(screen.getByTestId('policy-table')).toBeInTheDocument();
  });
});