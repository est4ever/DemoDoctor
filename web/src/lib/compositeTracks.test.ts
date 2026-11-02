import {expect,it} from "vitest";
import {compositeDisplayTracks} from "./compositeTracks";
import type {MultiCameraManifest,TracksBundle} from "./types";

it("translates box-local masks/boxes for display only and never merges camera identities",()=>{
  const manifest={source_mode:"composite",sources:[{source_video_id:"source1",width:200,height:100,fps:10,sha256:"source-hash"}],cameras:[{camera_id:"cam1",name:"Left",crop:[0,0,100,100],playback_offset_s:0},{camera_id:"cam2",name:"Right",crop:[100,0,100,100],playback_offset_s:0}]} as MultiCameraManifest;
  const track={episode_key:"live",source:"original",provenance:"observed",image_size:[100,100],fps:10,t_start:0,t_end:1,frame_start:0,frame_end:10,
    legend:[{object_id:"item:0",label:"item",color_rgb:[1,2,3]}],tracks:{'item:0':{object_id:"item:0",color_rgb:[1,2,3],n_observations:1,points:[{frame_index:2,t:.2,centroid:[12,22],bbox:[10,20,14,24]}]}},
    frames:{'2':[{object_id:"item:0",centroid:[12,22],bbox:[10,20,14,24],confidence:.9,track_status:"unknown",mask:{size:[4,4],counts:[0,16]}}]}} as TracksBundle;
  const original=JSON.stringify(track),result=compositeDisplayTracks(manifest,{cam1:track,cam2:track})!;
  expect(result.frames['2'].map(d=>d.object_id)).toEqual(['cam1/item:0','cam2/item:0']);
  expect(result.frames['2'][1].bbox).toEqual([110,20,114,24]);expect(result.frames['2'][1].centroid).toEqual([112,22]);
  expect(result.frames['2'][1].mask).toEqual({size:[4,4],counts:[0,16]});
  expect(result.tracks['cam2/item:0'].points[0].frame_index).toBe(2);
  expect(JSON.stringify(track)).toBe(original);expect(compositeDisplayTracks({...manifest,source_mode:"separate"},{cam1:track})).toBeNull();
});
