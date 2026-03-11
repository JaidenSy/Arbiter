import React, { useState } from 'react'

interface CopyButtonProps {
  text: string
}

function CopyButton({ text }: CopyButtonProps): React.ReactElement {
  const [copied, setCopied] = useState(false)

  const handleCopy = async (): Promise<void> => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="ml-2 px-3 py-1 text-xs font-medium rounded border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 transition-colors"
    >
      {copied ? 'Copied!' : 'Copy'}
    </button>
  )
}

export default CopyButton
