import type { InputHTMLAttributes } from "react";

type Props = InputHTMLAttributes<HTMLInputElement> & { label: string; name: string; error?: string };

export function DateField({ label, name, error, ...rest }: Props) {
  return (
    <div>
      <label htmlFor={name}>{label}</label>
      <input
        id={name}
        name={name}
        type="date"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${name}-err` : undefined}
        {...rest}
      />
      {error && (
        <p className="err" id={`${name}-err`} role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
