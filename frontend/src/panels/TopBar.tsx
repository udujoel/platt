import React from "react";
import { Bell, Search } from "lucide-react";
import type { PlattState } from "../backend-events";

export const navTitles: Record<string, string> = {
  overview: "Overview",
  jobs: "Jobs",
  provisioning: "Provisioning",
  pipelines: "PRs & Pipelines",
  moduleGraph: "Module Graph",
  boards: "Boards",
  audit: "Audit",
  approvals: "Approvals",
  settings: "Settings",
};

const stateLabels: Record<PlattState, string> = {
  idle: "Idle",
  listening: "Listening",
  thinking: "Thinking",
  working: "Working",
  talking: "Talking",
  awaiting_approval: "Awaiting approval",
  celebrating: "Celebrating",
  concerned: "Needs attention",
};

export function TopBar({
  title,
  plattState,
  alertCount,
  search,
  onSearchChange,
}: {
  title: string;
  plattState: PlattState;
  alertCount: number;
  search: string;
  onSearchChange: (value: string) => void;
}) {
  return (
    <header className="topBar">
      <h1 className="topBarTitle">{title}</h1>
      <div className="topBarSearch">
        <Search size={15} aria-hidden="true" />
        <input
          type="search"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search jobs, PRs, modules…"
          aria-label="Search dashboard"
        />
      </div>
      <div className="topBarActions">
        <button type="button" className="topBarBell" aria-label={`${alertCount} recent alerts`}>
          <Bell size={17} />
          {alertCount > 0 ? <span className="topBarBellBadge">{alertCount > 9 ? "9+" : alertCount}</span> : null}
        </button>
        <span className={`plattStatusPill ${plattState}`} aria-live="polite">
          <span className="plattStatusDot" aria-hidden="true" />
          Platt is {stateLabels[plattState].toLowerCase()}
        </span>
      </div>
    </header>
  );
}
