import React from "react";
import { ProvisioningCard } from "./ProvisioningCard";
import { RepositoryPanel } from "./RepositoryPanel";
import type { OnboardingRecord } from "./RepositoryPanel";
import type { BackendEvent } from "../backend-events";

export function ProvisioningView({
  lastEvent,
  onboardingRecord,
  onOnboardingRecordChange,
  onPlanJobAccepted,
  postJson,
}: {
  lastEvent: BackendEvent | null;
  onboardingRecord: OnboardingRecord | null;
  onOnboardingRecordChange: (record: OnboardingRecord) => void;
  onPlanJobAccepted: (jobId: string) => void;
  postJson: <T>(path: string, body?: unknown) => Promise<T>;
}) {
  return (
    <div className="provisioningViewGrid">
      <ProvisioningCard lastEvent={lastEvent} />
      <RepositoryPanel
        record={onboardingRecord}
        onRecordChange={onOnboardingRecordChange}
        onPlanJobAccepted={onPlanJobAccepted}
        postJson={postJson}
      />
    </div>
  );
}
