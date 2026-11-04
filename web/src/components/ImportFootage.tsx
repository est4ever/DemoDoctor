import { LiveAnalyzePanel } from "./LiveAnalyzePanel";
import { RecentInvestigations } from "./RecentInvestigations";
import type { AnalysisBundle, TracksBundle } from "../lib/types";
import type { UploadDraftStore } from "../lib/uploadDraft";

export function ImportFootage({onLiveResult,draftStore}:{onLiveResult:(r:{jobId:string;analysis:AnalysisBundle;tracks:TracksBundle|null})=>void;draftStore?:UploadDraftStore}) {
  return <><RecentInvestigations/><LiveAnalyzePanel onLiveResult={onLiveResult} draftStore={draftStore}/></>;
}
