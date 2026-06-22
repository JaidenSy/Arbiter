import React from "react";

export type BadgeVariant = "success" | "neutral" | "error" | "accent" | "warning";

// Tokenized badges: zinc neutrals and amber accent, no green/red literals
const variantClasses: Record<BadgeVariant, string> = {
  success: "bg-success/10 text-success border border-success/25",
  neutral: "bg-elevated text-secondary border border-border-strong",
  error:   "bg-error/10 text-error border border-error/25",
  accent:  "bg-accent/10 text-accent-light border border-border-accent",
  warning: "bg-warning/10 text-warning border border-warning/25",
};

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
}

function Badge({ variant, children }: BadgeProps): React.ReactElement {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-mono ${variantClasses[variant]}`}
    >
      {children}
    </span>
  );
}

export default Badge;
