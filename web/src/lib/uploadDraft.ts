import { useEffect, useRef, type MutableRefObject } from "react";
import type { CameraInputDraft } from "../components/CameraInputs";

export type UploadDraft = {
  file: File | null; task: string; questions: string; objectConcept: string; destination: string;
  windowStart: string; windowEnd: string; useWindow: boolean; completeDemo: boolean;
  mode: "dry" | "real"; cameras: CameraInputDraft; dirty: boolean;
};
export type UploadDraftStore = MutableRefObject<UploadDraft | null>;

/** Memory only: file handles, settings and prompts survive route remounts, never a reload.
 * Refresh/close requires a native discard confirmation. No credentials or approvals belong here.
 */
export function useUploadDraftStore(existing?: UploadDraftStore): UploadDraftStore {
  const local = useRef<UploadDraft | null>(null);
  const store = existing ?? local;
  useEffect(() => {
    if (existing) return;
    const warn = (event: BeforeUnloadEvent) => {
      if (!store.current?.dirty) return;
      event.preventDefault(); event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [existing, store]);
  return store;
}
