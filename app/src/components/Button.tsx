import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

type Props = ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode; variant?: "primary" | "secondary" };

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { children, variant = "primary", ...rest }: Props,
  ref,
) {
  return (
    <button ref={ref} className={variant === "secondary" ? "secondary" : undefined} {...rest}>
      {children}
    </button>
  );
});
