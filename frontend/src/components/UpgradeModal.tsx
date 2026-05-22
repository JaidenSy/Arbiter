/**
 * Arbiter — UpgradeModal.
 *
 * Listens for the global `arbiter:plan_limit` CustomEvent (dispatched by
 * the Axios interceptors in api/client.ts whenever the backend returns 402)
 * and shows a modal directing the user to upgrade.
 */

import React, { useEffect, useState } from "react";
import Modal from "./Modal";
import { PLAN_LIMIT_EVENT, type PlanLimitPayload } from "../api/client";

export default function UpgradeModal(): React.ReactElement | null {
  const [payload, setPayload] = useState<PlanLimitPayload | null>(null);

  useEffect(() => {
    const handler = (e: Event): void => {
      setPayload((e as CustomEvent<PlanLimitPayload>).detail);
    };
    window.addEventListener(PLAN_LIMIT_EVENT, handler);
    return () => window.removeEventListener(PLAN_LIMIT_EVENT, handler);
  }, []);

  if (!payload) return null;

  const resourceLabel = payload.resource.replace(/_/g, " ");

  return (
    <Modal isOpen onClose={() => setPayload(null)} title="Plan Limit Reached">
      <div className="space-y-5">
        <div className="rounded-lg bg-warning/10 border border-warning/20 px-4 py-3">
          <p className="text-warning text-sm font-semibold capitalize">{resourceLabel}</p>
          <p className="text-secondary text-xs mt-1">
            {payload.current} of {payload.limit} used on the <span className="text-primary font-semibold capitalize">{payload.plan}</span> plan.
          </p>
        </div>

        <p className="text-secondary text-sm">
          Upgrade to <span className="text-accent-light font-semibold">Pro</span> for higher limits and priority support.
        </p>

        <div className="flex gap-3 pt-1">
          <a
            href="https://arbiterai.dev/pricing"
            target="_blank"
            rel="noopener noreferrer"
            className="press flex-1 bg-accent hover:bg-accent-light text-white text-center py-2.5 rounded-lg text-sm font-semibold transition-[background-color,box-shadow] duration-150 ease-[var(--ease-out-expo)] hover:shadow-[0_0_16px_rgba(217,119,6,0.30)]"
          >
            Upgrade to Pro
          </a>
          <button
            onClick={() => setPayload(null)}
            className="press flex-1 border border-border-strong hover:border-white/[0.22] text-secondary hover:text-primary py-2.5 rounded-lg text-sm transition-colors duration-150 ease-[var(--ease-out-expo)]"
          >
            Maybe Later
          </button>
        </div>
      </div>
    </Modal>
  );
}
