import { describe, expect, it } from "vitest";

import { CharacterErrorBoundary } from "./CharacterErrorBoundary";

describe("CharacterErrorBoundary", () => {
  it("starts without an error, rendering children", () => {
    const boundary = new CharacterErrorBoundary({ fallback: "fallback", children: "children" });
    expect(boundary.state).toEqual({ hasError: false });
    expect(boundary.render()).toBe("children");
  });

  it("derives hasError from a thrown error (e.g. a missing/corrupt platt.glb)", () => {
    expect(CharacterErrorBoundary.getDerivedStateFromError()).toEqual({ hasError: true });
  });

  it("renders the fallback once hasError is set", () => {
    const boundary = new CharacterErrorBoundary({ fallback: "fallback", children: "children" });
    boundary.state = CharacterErrorBoundary.getDerivedStateFromError();
    expect(boundary.render()).toBe("fallback");
  });
});
