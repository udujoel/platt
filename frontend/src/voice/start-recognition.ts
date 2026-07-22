/**
 * `SpeechRecognition#start()` can throw synchronously — e.g. `InvalidStateError` when it's
 * called while a recognition session is already starting/running — in addition to reporting
 * async failures via `onerror`. Wrapping it here lets the caller (the `useSpeechRecognition`
 * hook) roll back the optimistic "listening" state instead of getting stuck showing a mic that
 * never actually started.
 */
export function startRecognitionSafely(recognition: Pick<SpeechRecognitionLike, "start">): boolean {
  try {
    recognition.start();
    return true;
  } catch {
    return false;
  }
}
