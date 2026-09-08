import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Eye, EyeOff } from 'lucide-react';
import { checkPasswordComplexity } from '../utils/password';

interface PasswordFieldProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
  id?: string;
  autoFocus?: boolean;
  /**
   * Check the value against the complexity rules and name the first unmet one
   * as the user types. Off for "current password" fields, where the rules
   * describe the NEW password and an old one that predates them is still valid.
   */
  showRules?: boolean;
  /** When given and different from `value`, the field says they do not match. */
  mustMatch?: string;
  // ⚠️ `required` is the HTML attribute only — it deliberately draws no
  // asterisk. Forms in this codebase mark their own required fields (the
  // advanced-auth user dialog puts a red `*` in the label itself), and a
  // component that added one of its own put an asterisk on the login page's
  // password beside an unmarked username.
}

/**
 * One password input: reveal toggle, and the reason it is not accepted yet.
 *
 * ⚠️ The reason is the point of this component. Every create/change form
 * disabled its submit button on `isPasswordValid(...)` while the message
 * explaining WHICH rule failed lived in the click handler — behind the button
 * that same rule had disabled. So a user typing a password that was merely too
 * short saw a dead button and no text anywhere: the explanation existed and was
 * unreachable by construction (reported 2026-09-08).
 *
 * The rules come from `utils/password.ts`, which mirrors the backend validator.
 * Nothing here may grow its own threshold: two forms had hand-rolled
 * `length < 6` checks while the server required 8 plus a mix, so they let a
 * password through that the API then refused.
 */
export function PasswordField({
  label,
  value,
  onChange,
  placeholder,
  autoComplete = 'new-password',
  required,
  id,
  autoFocus,
  showRules,
  mustMatch,
}: PasswordFieldProps) {
  const { t } = useTranslation();
  const [revealed, setRevealed] = useState(false);
  const generatedId = useId();
  const inputId = id ?? generatedId;

  // Say nothing until there is something to say about: an empty field is not
  // yet a mistake, it is a field the user has not reached.
  const ruleKey = showRules && value ? checkPasswordComplexity(value) : null;
  const mismatch = mustMatch !== undefined && value.length > 0 && value !== mustMatch;
  const message = ruleKey ? t(ruleKey) : mismatch ? t('settings.passwordsDoNotMatch') : null;

  return (
    <div>
      <label htmlFor={inputId} className="block text-sm font-medium text-white mb-2">
        {label}
      </label>
      <div className="relative">
        <input
          id={inputId}
          type={revealed ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className={`block w-full px-4 py-3 pr-12 bg-bambu-dark-secondary border rounded-lg text-white placeholder-bambu-gray focus:outline-none focus:ring-2 focus:ring-bambu-green/50 focus:border-bambu-green transition-colors ${
            message ? 'border-red-500' : 'border-bambu-dark-tertiary'
          }`}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          autoFocus={autoFocus}
          aria-invalid={message ? true : undefined}
          aria-describedby={message ? `${inputId}-hint` : undefined}
        />
        <button
          type="button"
          onClick={() => setRevealed(!revealed)}
          className="absolute right-3 top-1/2 -translate-y-1/2 text-bambu-gray hover:text-white transition-colors"
          // Out of the tab order on purpose: tabbing from the password field
          // should reach the next field, not a view toggle.
          tabIndex={-1}
          aria-label={t(revealed ? 'common.hidePassword' : 'common.showPassword')}
          title={t(revealed ? 'common.hidePassword' : 'common.showPassword')}
        >
          {revealed ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
        </button>
      </div>
      {message && (
        <p id={`${inputId}-hint`} className="text-red-700 dark:text-red-400 text-xs mt-1">
          {message}
        </p>
      )}
    </div>
  );
}
