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
      className={`text-xs border px-2 py-1 rounded font-mono transition-colors ${
        copied
          ? "text-green-400 border-green-400/30"
          : "text-secondary hover:text-primary border-white/10 hover:border-white/20"
      }`}
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

export default CopyButton;
