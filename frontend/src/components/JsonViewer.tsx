/**
 * NexVault — JsonViewer component.
 *
 * Renders a pretty-printed, scrollable JSON block.
 * If data is null, renders a muted "null" placeholder.
 * No external dependencies.
 */

import React from "react";

interface JsonViewerProps {
  data: Record<string, unknown> | null;
  /** CSS max-height value. Defaults to "200px". */
  maxHeight?: string;
}

function JsonViewer({ data, maxHeight = "200px" }: JsonViewerProps): React.ReactElement {
  if (data === null) {
    return <span className="text-muted font-mono text-xs">null</span>;
  }

  return (
    <pre
      className="font-mono text-xs text-secondary bg-base border border-white/[0.07] rounded p-3 overflow-y-auto"
      style={{ maxHeight }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

export default JsonViewer;
