/**
 * Tests for PasswordField — the shared account-password input.
 *
 * The regression these guard against: every create/change-password form
 * disabled its submit button on the complexity rules while the only message
 * naming the unmet rule lived behind that same button, so a rejected password
 * produced a grey button and no text anywhere on screen.
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { render } from '../utils';
import { PasswordField } from '../../components/PasswordField';

describe('PasswordField', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('masks the value and reveals it on demand', async () => {
    const user = userEvent.setup();
    render(
      <PasswordField label="Password" value="hunter2" onChange={vi.fn()} />
    );

    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('type', 'password');

    await user.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');

    await user.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(input).toHaveAttribute('type', 'password');
  });

  it('names the first unmet rule while the user types', () => {
    render(
      <PasswordField label="Password" value="short" onChange={vi.fn()} showRules />
    );
    expect(
      screen.getByText('Password must be at least 8 characters')
    ).toBeInTheDocument();
  });

  it('moves on to the next rule once the length is satisfied', () => {
    render(
      <PasswordField label="Password" value="lowercase1" onChange={vi.fn()} showRules />
    );
    expect(
      screen.getByText('Password must contain at least one uppercase letter')
    ).toBeInTheDocument();
  });

  it('says nothing about an empty field', () => {
    const { container } = render(
      <PasswordField label="Password" value="" onChange={vi.fn()} showRules />
    );
    // An untouched field is not a mistake — it is one the user has not reached.
    expect(container.querySelector('p')).toBeNull();
  });

  it('stays silent without showRules, for a current-password field', () => {
    // The rules describe the NEW password; an account that predates them still
    // signs in with what it has.
    const { container } = render(
      <PasswordField label="Current" value="old" onChange={vi.fn()} />
    );
    expect(container.querySelector('p')).toBeNull();
  });

  it('reports a confirmation that does not match', () => {
    render(
      <PasswordField
        label="Confirm"
        value="Abcdef12"
        onChange={vi.fn()}
        mustMatch="Abcdef13"
      />
    );
    expect(screen.getByText('Passwords do not match')).toBeInTheDocument();
  });

  it('accepts a matching confirmation', () => {
    const { container } = render(
      <PasswordField
        label="Confirm"
        value="Abcdef12"
        onChange={vi.fn()}
        mustMatch="Abcdef12"
      />
    );
    expect(container.querySelector('p')).toBeNull();
  });

  it('wires the message to the input for screen readers', () => {
    render(
      <PasswordField id="pw" label="Password" value="short" onChange={vi.fn()} showRules />
    );
    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-describedby', 'pw-hint');
    expect(document.getElementById('pw-hint')).toHaveTextContent(
      'Password must be at least 8 characters'
    );
  });

  it('keeps the reveal button out of the tab order', () => {
    // Tabbing out of a password field should reach the next field, not a
    // control that only changes how this one looks.
    render(<PasswordField label="Password" value="x" onChange={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Show password' })).toHaveAttribute(
      'tabindex',
      '-1'
    );
  });

  it('reports every keystroke', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<PasswordField label="Password" value="" onChange={onChange} />);
    await user.type(screen.getByLabelText('Password'), 'a');
    expect(onChange).toHaveBeenCalledWith('a');
  });
});
