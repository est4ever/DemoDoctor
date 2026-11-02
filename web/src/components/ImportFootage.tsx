import { LiveAnalyzePanel } from "./LiveAnalyzePanel";
import { RecentInvestigations } from "./RecentInvestigations";
import type { AnalysisBundle, TracksBundle } from "../lib/types";

export function ImportFootage({onLiveResult}:{onLiveResult:(r:{jobId:string;analysis:AnalysisBundle;tracks:TracksBundle|null})=>void}) {
  return <><RecentInvestigations/><LiveAnalyzePanel onLiveResult={onLiveResult}/></>;
}
