export const INITIAL_RETRY_DELAY_MS = 1_000;
export const MAX_RETRY_DELAY_MS = 10_000;

export class ReconnectPolicy {
  private attempt = 0;

  nextDelayMs() {
    const delay = Math.min(INITIAL_RETRY_DELAY_MS * 2 ** this.attempt, MAX_RETRY_DELAY_MS);
    this.attempt += 1;
    return delay;
  }

  reset() {
    this.attempt = 0;
  }
}
