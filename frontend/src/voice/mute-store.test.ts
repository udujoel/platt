import { describe, expect, it } from "vitest";

import { MUTE_STORAGE_KEY, type MuteStorage, readPersistedMute, writePersistedMute } from "./mute-store";

function fakeStorage(initial: Record<string, string> = {}): MuteStorage {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => {
      data.set(key, value);
    },
  };
}

function throwingStorage(): MuteStorage {
  return {
    getItem: () => {
      throw new Error("storage disabled");
    },
    setItem: () => {
      throw new Error("storage disabled");
    },
  };
}

describe("readPersistedMute", () => {
  it("reads unmuted when nothing has been stored yet", () => {
    expect(readPersistedMute(fakeStorage())).toBe(false);
  });

  it("reads the persisted muted flag", () => {
    expect(readPersistedMute(fakeStorage({ [MUTE_STORAGE_KEY]: "1" }))).toBe(true);
  });

  it("reads unmuted for any non-'1' stored value", () => {
    expect(readPersistedMute(fakeStorage({ [MUTE_STORAGE_KEY]: "0" }))).toBe(false);
  });

  it("degrades to unmuted when storage throws", () => {
    expect(readPersistedMute(throwingStorage())).toBe(false);
  });
});

describe("writePersistedMute", () => {
  it("round-trips true through storage", () => {
    const storage = fakeStorage();
    writePersistedMute(storage, true);
    expect(readPersistedMute(storage)).toBe(true);
  });

  it("round-trips false through storage", () => {
    const storage = fakeStorage({ [MUTE_STORAGE_KEY]: "1" });
    writePersistedMute(storage, false);
    expect(readPersistedMute(storage)).toBe(false);
  });

  it("does not throw when storage is unavailable", () => {
    expect(() => writePersistedMute(throwingStorage(), true)).not.toThrow();
  });
});
