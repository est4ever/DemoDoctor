import { describe, expect, it } from "vitest";
import { criterionContextTime } from "./criterionContext";
import type { CriterionContextFrame, MultiCameraManifest } from "./types";
const manifest: MultiCameraManifest = {duration_s:10,alignment:{kind:"approved",basis:"flash",convention:"offset"},limitations:[],cameras:[
  {camera_id:"cam2",name:"side",motion:"static",source_video_id:"source2",playback_offset_s:1,offset_s:1,fps:15,width:1280,height:720,frame_start:15,frame_end:150,sha256:"hash",crop:null}]};
const frame: CriterionContextFrame={frame_ref:"C0",camera_id:"cam2",source_video_id:"source2",original_frame:45,original_timestamp_s:3,shared_timestamp_s:2,scope:"context only"};
describe("criterion frame provenance and seeking",()=>{
  it("seeks shared time while retaining the supporting camera",()=>expect(criterionContextTime(frame,manifest)).toBe(2));
  it.each([{camera_id:"cam1"},{source_video_id:"source1"},{original_frame:151},{original_frame:14},{shared_timestamp_s:3},{original_timestamp_s:0},{original_frame:45.5}])("rejects another camera/source, unprocessed frame or inconsistent timestamp: %j", change=>{
    expect(criterionContextTime({...frame,...change},manifest)).toBeNull();
  });
});
