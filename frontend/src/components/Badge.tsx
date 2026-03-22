import React from "react";

export type BadgeVariant = "success" | "neutral" | "error";

const variantClasses: Record<BadgeVariant, string> = {
  success: "bg-green-100 text-green-800",
  neutral: "bg-gray-100 text-gray-700",
  error: "bg-red-100 text-red-800",
};

interface BadgeProps {
  variant: BadgeVariant;
  children: React.ReactNode;
}

function Badge({ variant, children }: BadgeProps): React.ReactElement {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${variantClasses[variant]}`}
    >
      {children}
    </span>
  );
}

export default Badge;
