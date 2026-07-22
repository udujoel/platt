import { create } from "zustand";

export const MUTE_STORAGE_KEY = "platt.voice.muted";

export type MuteStorage = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
};

/** Reads the persisted mute flag; any storage failure (private mode, disabled storage) reads as unmuted. */
export function readPersistedMute(storage: MuteStorage): boolean {
  try {
    return storage.getItem(MUTE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

/** Writes the mute flag; a storage failure is swallowed since it only means the choice won't survive a reload. */
export function writePersistedMute(storage: MuteStorage, muted: boolean): void {
  try {
    storage.setItem(MUTE_STORAGE_KEY, muted ? "1" : "0");
  } catch {
    // storage unavailable — mute state just won't persist across reloads
  }
}

const noopStorage: MuteStorage = { getItem: () => null, setItem: () => undefined };

/** `window.localStorage` can throw (sandboxed iframes, storage-blocked contexts) just from the getter, not only on use. */
function safeLocalStorage(): MuteStorage {
  try {
    return typeof window !== "undefined" && window.localStorage ? window.localStorage : noopStorage;
  } catch {
    return noopStorage;
  }
}

type VoiceMuteState = {
  muted: boolean;
  toggleMute: () => void;
  setMuted: (muted: boolean) => void;
};

/** Zustand store wiring `readPersistedMute`/`writePersistedMute` to real `localStorage` for the mute toggle UI. */
export const useVoiceMuteStore = create<VoiceMuteState>((set, get) => ({
  muted: readPersistedMute(safeLocalStorage()),
  toggleMute: () => {
    const next = !get().muted;
    writePersistedMute(safeLocalStorage(), next);
    set({ muted: next });
  },
  setMuted: (muted) => {
    writePersistedMute(safeLocalStorage(), muted);
    set({ muted });
  },
}));
