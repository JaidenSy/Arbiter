import React, { useState } from "react";

interface CopyButtonProps {
  text: string;
}

function CopyButton({ text }: CopyButtonProps): React.ReactElement {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (): Promise<void> => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      type="button"
      onClick={handleCopy}
      className={`press text-xs border px-2 py-1 rounded font-mono transition-colors duration-150 ease-[var(--ease-out-expo)] ${
        copied
          ? "text-success border-success/30"
          : "text-secondary hover:text-primary border-border-strong hover:border-white/[0.22]"
      }`}
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

export default CopyButton;
