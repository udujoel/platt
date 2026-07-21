import React from "react";

type Props = {
  fallback: React.ReactNode;
  children: React.ReactNode;
};

type State = {
  hasError: boolean;
};

/**
 * Catches `platt.glb` load failures thrown by drei's `useGLTF` inside `Suspense` (a rejected
 * loader promise surfaces as a thrown error on the next render, not a Suspense fallback) and
 * swaps to the procedural rig so a missing/corrupt asset never blanks the scene.
 */
export class CharacterErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}
