import React from "react";
import { deriveProvisionSteps, useProvisionStore } from "./provision-store";
import type { BackendEvent } from "../backend-events";

export function ProvisionTimeline({ lastEvent }: { lastEvent: BackendEvent | null }) {
  const events = useProvisionStore((store) => store.events);
  const applyEvent = useProvisionStore((store) => store.applyEvent);

  React.useEffect(() => {
    if (lastEvent) applyEvent(lastEvent);
  }, [applyEvent, lastEvent]);

  const steps = deriveProvisionSteps(events);
  if (steps.every((step) => step.status === "pending")) return null;

  return (
    <ol className="provisionTimeline" aria-label="Provision job progress">
      {steps.map((step) => (
        <li key={step.id} className={`provisionStep ${step.status}`}>
          <span className="provisionStepDot" aria-hidden="true" />
          <span className="provisionStepLabel">{step.label}</span>
        </li>
      ))}
    </ol>
  );
}
