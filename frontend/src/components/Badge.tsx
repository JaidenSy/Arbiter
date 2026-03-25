import React from "react";

export type BadgeVariant = "success" | "neutral" | "error";

const variantClasses: Record<BadgeVariant, string> = {
  success: "bg-green-950 text-green-400 border border-green-900",
  neutral: "bg-white/5 text-secondary border border-white/10",
  error: "bg-red-950 text-red-400 border border-red-900",
};

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
}

function Badge({ variant, children }: BadgeProps): React.ReactElement {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-mono ${variantClasses[variant]}`}
    >
      {children}
    </span>
  );
}

export default Badge;
