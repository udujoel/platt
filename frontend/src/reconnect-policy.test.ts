import { describe, expect, it } from "vitest";

import { INITIAL_RETRY_DELAY_MS, MAX_RETRY_DELAY_MS, ReconnectPolicy } from "./reconnect-policy";

describe("ReconnectPolicy", () => {
  it("backs off exponentially and caps the retry delay", () => {
    const policy = new ReconnectPolicy();

    expect([policy.nextDelayMs(), policy.nextDelayMs(), policy.nextDelayMs(), policy.nextDelayMs(), policy.nextDelayMs()]).toEqual([
      INITIAL_RETRY_DELAY_MS,
      2_000,
      4_000,
      8_000,
      MAX_RETRY_DELAY_MS,
    ]);
    expect(policy.nextDelayMs()).toBe(MAX_RETRY_DELAY_MS);
  });

  it("returns to the initial delay only after the caller marks the connection stable", () => {
    const policy = new ReconnectPolicy();

    policy.nextDelayMs();
    policy.nextDelayMs();
    policy.reset();

    expect(policy.nextDelayMs()).toBe(INITIAL_RETRY_DELAY_MS);
  });
});
