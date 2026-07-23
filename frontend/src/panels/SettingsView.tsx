import React from "react";
import { MuteToggle } from "../voice/MuteToggle";
import type { BackendReadiness } from "../readiness-status";

export function SettingsView({ apiBaseUrl, readiness }: { apiBaseUrl: string; readiness: BackendReadiness }) {
  return (
    <div className="settingsViewGrid">
      <section className="dashCard" aria-labelledby="settings-voice-heading">
        <header className="dashCardHeader">
          <h2 id="settings-voice-heading">Voice</h2>
        </header>
        <div className="settingsRow">
          <div>
            <strong>Speech output</strong>
            <p>Mute or unmute Platt's spoken replies.</p>
          </div>
          <MuteToggle />
        </div>
      </section>

      <section className="dashCard" aria-labelledby="settings-backend-heading">
        <header className="dashCardHeader">
          <h2 id="settings-backend-heading">Backend</h2>
        </header>
        <dl className="settingsDetails">
          <div><dt>API base URL</dt><dd>{apiBaseUrl}</dd></div>
          <div><dt>Readiness</dt><dd className={`readinessBadge ${readiness}`}>{readiness}</dd></div>
          <div><dt>Environment</dt><dd>Sandbox</dd></div>
        </dl>
      </section>
    </div>
  );
}
