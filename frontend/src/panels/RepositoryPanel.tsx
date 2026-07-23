import React from "react";

export type OnboardingModuleNode = { path: string; variables: string[]; outputs: string[] };
export type OnboardingPipeline = { file_path: string };
export type OnboardingRecord = {
  id: string;
  repository_path: string;
  created_at: string;
  files: Array<{ path: string; size_bytes: number }>;
  terraform_module_nodes: OnboardingModuleNode[];
  pipeline_yamls: OnboardingPipeline[];
};

export type RepositoryInspectionStep = {
  id: string;
  title: string;
  tool: "read_file" | "glob" | "grep";
  arguments: Record<string, string>;
  expected_output: string;
};
export type RepositoryInspectionPlan = { summary: string; steps: RepositoryInspectionStep[] };
export type RepositoryToolResponse = { tool: "read_file" | "glob" | "grep"; result: unknown };

function repositoryName(path: string) {
  const segments = path.split("/").filter(Boolean);
  return segments[segments.length - 1] ?? path;
}

function formatRepositoryToolResult(result: unknown) {
  const output = JSON.stringify(result, null, 2);
  return output.length > 1_600 ? `${output.slice(0, 1_600)}\n… truncated in preview` : output;
}

export function RepositoryPanel({
  record,
  onRecordChange,
  onPlanJobAccepted,
  postJson,
}: {
  record: OnboardingRecord | null;
  onRecordChange: (record: OnboardingRecord) => void;
  onPlanJobAccepted: (jobId: string) => void;
  postJson: <T>(path: string, body?: unknown) => Promise<T>;
}) {
  const [repositoryPath, setRepositoryPath] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [plan, setPlan] = React.useState<RepositoryInspectionPlan | null>(null);
  const [planJobId, setPlanJobId] = React.useState<string | null>(null);
  const [planBusy, setPlanBusy] = React.useState(false);
  const [planError, setPlanError] = React.useState<string | null>(null);
  const [runningStepId, setRunningStepId] = React.useState<string | null>(null);
  const [stepResults, setStepResults] = React.useState<Record<string, RepositoryToolResponse>>({});
  const [stepError, setStepError] = React.useState<string | null>(null);
  const modulePreview = record?.terraform_module_nodes.slice(0, 3).map((module) => (module.path === "." ? "root" : module.path)).join(", ");

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const path = repositoryPath.trim();
    if (!path || busy) return;

    setBusy(true);
    setError(null);
    try {
      const response = await postJson<OnboardingRecord>("/onboarding", { repository_path: path });
      setPlan(null);
      setPlanJobId(null);
      setPlanError(null);
      setStepResults({});
      setStepError(null);
      onRecordChange(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not onboard this repository.");
    } finally {
      setBusy(false);
    }
  };

  const onPreparePlan = async () => {
    if (!record || planBusy) return;

    setPlanBusy(true);
    setPlanError(null);
    try {
      const response = await postJson<{ job_id: string; plan: RepositoryInspectionPlan }>(
        `/onboarding/${encodeURIComponent(record.id)}/plans/repository-review`,
      );
      setPlan(response.plan);
      setPlanJobId(response.job_id);
      setStepResults({});
      setStepError(null);
      onPlanJobAccepted(response.job_id);
    } catch (reason) {
      setPlanError(reason instanceof Error ? reason.message : "Could not prepare this review plan.");
    } finally {
      setPlanBusy(false);
    }
  };

  const onRunPlanStep = async (step: RepositoryInspectionStep) => {
    if (!record || !planJobId || runningStepId) return;

    setRunningStepId(step.id);
    setStepError(null);
    try {
      const response = await postJson<RepositoryToolResponse>(
        `/onboarding/${encodeURIComponent(record.id)}/plans/repository-review/${encodeURIComponent(planJobId)}/steps/${encodeURIComponent(step.id)}`,
      );
      setStepResults((current) => ({ ...current, [step.id]: response }));
    } catch (reason) {
      setStepError(reason instanceof Error ? reason.message : "Could not run this read-only step.");
    } finally {
      setRunningStepId(null);
    }
  };

  return (
    <section className="dashCard repositoryPanelCard" aria-labelledby="repository-heading">
      <header className="dashCardHeader">
        <h2 id="repository-heading">Onboard a local repo</h2>
        <span className={`repositoryStatus ${record ? "ready" : ""}`}>{record ? "Ready" : "Local only"}</span>
      </header>
      <p className="repositoryIntro">Index a checked-out repository that is inside the backend's configured onboarding root. Platt only reads its bounded inventory.</p>
      <form className="onboardingForm" onSubmit={onSubmit}>
        <label htmlFor="repository-path">Repository path</label>
        <div>
          <input
            id="repository-path"
            value={repositoryPath}
            disabled={busy}
            onChange={(event) => setRepositoryPath(event.target.value)}
            placeholder="/workspace/checked-out-repository"
          />
          <button type="submit" disabled={busy || !repositoryPath.trim()}>{busy ? "Indexing" : "Onboard"}</button>
        </div>
      </form>
      {error ? <div className="repositoryError" role="alert">{error}</div> : null}
      {record ? (
        <div className="repositorySummary" aria-live="polite">
          <strong title={record.repository_path}>{repositoryName(record.repository_path)}</strong>
          <span>{record.repository_path}</span>
          <dl>
            <div><dt>Files</dt><dd>{record.files.length}</dd></div>
            <div><dt>Modules</dt><dd>{record.terraform_module_nodes.length}</dd></div>
            <div><dt>Pipelines</dt><dd>{record.pipeline_yamls.length}</dd></div>
          </dl>
          {modulePreview ? <p>Graph: {modulePreview}{record.terraform_module_nodes.length > 3 ? "…" : ""}</p> : <p>No Terraform module graph found.</p>}
          <button className="planButton" type="button" onClick={() => void onPreparePlan()} disabled={planBusy}>
            {planBusy ? "Preparing plan" : "Prepare review plan"}
          </button>
          {planError ? <div className="repositoryError" role="alert">{planError}</div> : null}
          {plan ? (
            <section className="reviewPlan" aria-labelledby="review-plan-heading">
              <header>
                <div>
                  <p className="eyebrow">Read-only review</p>
                  <h2 id="review-plan-heading">Proposed tool plan</h2>
                </div>
                <span>{plan.steps.length} steps</span>
              </header>
              <p>{plan.summary}</p>
              <ol>
                {plan.steps.map((step) => (
                  <li key={step.id}>
                    <strong>{step.title}</strong>
                    <span><b>{step.tool}</b> · {Object.entries(step.arguments).map(([name, value]) => `${name}: ${value}`).join(", ")}</span>
                    <small>{step.expected_output}</small>
                    <button className="planStepButton" type="button" onClick={() => void onRunPlanStep(step)} disabled={Boolean(runningStepId)}>
                      {runningStepId === step.id ? "Running read-only step" : `Run ${step.tool}`}
                    </button>
                    {stepResults[step.id] ? <pre>{formatRepositoryToolResult(stepResults[step.id].result)}</pre> : null}
                  </li>
                ))}
              </ol>
              {stepError ? <div className="repositoryError" role="alert">{stepError}</div> : null}
              <footer>No step runs automatically. Each explicit run is read-only and recorded against this plan job.</footer>
            </section>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
