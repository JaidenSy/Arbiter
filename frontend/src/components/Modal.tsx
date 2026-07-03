import React, { useEffect } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

function Modal({
  isOpen,
  onClose,
  title,
  children,
}: ModalProps): React.ReactElement | null {
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent): void => {
      if (e.key === "Escape") onClose();
    };

    document.body.style.overflow = 'hidden';
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.body.style.overflow = '';
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 overflow-y-auto"
      aria-modal="true"
      role="dialog"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="backdrop-enter fixed inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Centering wrapper: min-h-full keeps items-center working even when content overflows */}
      <div className="flex min-h-full items-center justify-center p-4">

      {/* Dialog */}
      <div className="modal-enter relative z-10 glass-surface border border-border-strong rounded-2xl w-full max-w-md shadow-2xl flex flex-col max-h-[calc(100vh-2rem)]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border flex-shrink-0">
          <h2 id="modal-title" className="font-display text-primary text-sm font-semibold tracking-tight">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="press text-muted hover:text-primary w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/[0.05] transition-colors duration-150 ease-[var(--ease-out-expo)]"
            aria-label="Close modal"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 overflow-y-auto">
          {children}
        </div>
      </div>

      </div>
    </div>
  , document.body);
}

export default Modal;
