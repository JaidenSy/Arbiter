import React from "react";
import Modal from "./Modal";

interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
}

function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
}: ConfirmDialogProps): React.ReactElement | null {
  const handleConfirm = (): void => {
    onConfirm();
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <p className="text-sm text-secondary mb-6">{message}</p>
      <div className="flex justify-end gap-3">
        <button
          type="button"
          onClick={onClose}
          className="press text-secondary hover:text-primary hover:bg-white/[0.05] px-3 py-1.5 rounded text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleConfirm}
          className="press text-error hover:bg-error/10 px-3 py-1.5 rounded text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export default ConfirmDialog;
