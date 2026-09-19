import type { SelectHTMLAttributes } from "react";

type Props = SelectHTMLAttributes<HTMLSelectElement> & { label: string; name: string; options: string[]; error?: string };

export function Select({ label, name, options, error, ...rest }: Props) {
  return (
    <div>
      <label htmlFor={name}>{label}</label>
      <select
        id={name}
        name={name}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${name}-err` : undefined}
        {...rest}
      >
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
      {error && (
        <p className="err" id={`${name}-err`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
