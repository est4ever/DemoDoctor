import { useEffect, useRef, useState } from "react";
import { Button } from "./ui";
import { suggestCameraLayout, type LayoutProposal } from "../lib/cameraLayout";

type Camera = {name:string;motion:"unknown"|"static"|"moving";offset_s:number;object_concept:string;destination_concept:string;crop:number[]};
const camera=(i:number):Camera=>({name:`Camera ${i+1}`,motion:"unknown",offset_s:0,object_concept:"green plate",destination_concept:"dish rack",crop:[0,0,640,480]});

/** Input state only. Preparation, payment approval, progress and recovery share LiveAnalyzePanel. */
export function useCameraInputs() {
  const [count,setCount]=useState(1),[sourceMode,setSourceMode]=useState("separate");
  const [cameras,setCameras]=useState([camera(0),camera(1),camera(2)]);
  const [files,setFiles]=useState<Array<File|undefined>>([]),[ready,setReady]=useState<boolean[]>([]);
  const [size,setSize]=useState<[number,number]>([0,0]),[cropsConfirmed,setCropsConfirmed]=useState(false);
  const [aligned,setAligned]=useState(false),[basis,setBasis]=useState("");
  const [proposal,setProposal]=useState<LayoutProposal|null>(null);
  useEffect(()=>{setCropsConfirmed(false);setAligned(false);},[count,sourceMode,cameras,files]);
  useEffect(()=>{setFiles([]);setReady([]);setSize([0,0]);setProposal(null);},[sourceMode]);
  const cameraSet=count>1||sourceMode==="composite";
  const chooseFile=(i:number,file?:File)=>{setFiles(v=>{const next=[...v];next[i]=file;return next;});setReady(v=>{const next=[...v];next[i]=false;return next;});if(sourceMode==="composite"){setSize([0,0]);setProposal(null);}};
  const change=(i:number,key:keyof Camera,value:Camera[keyof Camera])=>setCameras(v=>v.map((c,j)=>j===i?{...c,[key]:value}:c));
  const selected=sourceMode==="composite"?[files[0]]:Array.from({length:count},(_,i)=>files[i]);
  const previewReady=selected.every((f,i)=>f&&ready[i]);
  const validate=()=>{
    if(selected.some(f=>!f||!f.size||!f.name.toLowerCase().endsWith(".mp4")))return "Choose a non-empty MP4 for every selected source.";
    if(!previewReady)return "Preview every selected camera source before preparation.";
    if(sourceMode==="composite"&&(!size[0]||!cropsConfirmed))return "Inspect and confirm every crop boundary before preparation.";
    if(sourceMode==="separate"&&count>1&&(!aligned||basis.trim().length<8))return "Approve the per-camera offsets and describe the alignment basis.";
    if(cameras.slice(0,count).some(c=>!c.name.trim()||!c.object_concept.trim()||!c.destination_concept.trim()))return "Fill in each camera name, object prompt and destination prompt.";
    return null;
  };
  const form=(task:string,start:number,end:number,dry:boolean,questions="")=>{
    const data=new FormData();selected.forEach(f=>data.append("videos",f!));data.append("dry_run",String(dry));
    data.append("manifest",JSON.stringify({source_mode:sourceMode,task_description:task,
      cameras:cameras.slice(0,count).map(c=>({...c,crop:sourceMode==="composite"?c.crop:null,offset_s:sourceMode==="composite"?0:c.offset_s})),
      alignment_confirmed:aligned,alignment_basis:basis,crops_confirmed:cropsConfirmed,layout_proposal:proposal,investigation_questions:questions,window_start_s:start,window_end_s:end}));
    return data;
  };
  return {count,setCount,sourceMode,setSourceMode,cameras,setCameras,files,chooseFile,change,ready,setReady,size,setSize,cropsConfirmed,setCropsConfirmed,aligned,setAligned,basis,setBasis,proposal,setProposal,cameraSet,previewReady,validate,form};
}
type Setup=ReturnType<typeof useCameraInputs>;

function Preview({file,onReady,onSize,videoRef}:{file?:File;onReady:()=>void;onSize?:(w:number,h:number)=>void;videoRef?:React.RefObject<HTMLVideoElement|null>}) {
  const [src,setSrc]=useState<string>();
  useEffect(()=>{if(!file){setSrc(undefined);return;}const url=URL.createObjectURL(file);setSrc(url);return()=>URL.revokeObjectURL(url);},[file]);
  return src?<video ref={videoRef} src={src} controls muted playsInline style={{width:"100%",maxHeight:220,objectFit:"contain"}} onLoadedData={onReady} onLoadedMetadata={e=>onSize?.(e.currentTarget.videoWidth,e.currentTarget.videoHeight)}/>:null;
}

export function CameraInputs({setup:s,disabled}:{setup:Setup;disabled:boolean}) {
  const video=useRef<HTMLVideoElement>(null),lastSuggestion=useRef(""),lastFile=useRef<File|undefined>(undefined);
  const [arrangement,setArrangement]=useState<"auto"|"horizontal"|"vertical">("auto"),[suggestionError,setSuggestionError]=useState("");
  const suggest=()=>{
    const v=video.current;if(!v||v.readyState<2)return;
    try {
      const scale=Math.min(1,Math.sqrt(8_000_000/(v.videoWidth*v.videoHeight))),canvas=document.createElement("canvas");
      canvas.width=Math.max(1,Math.round(v.videoWidth*scale));canvas.height=Math.max(1,Math.round(v.videoHeight*scale));
      const ctx=canvas.getContext("2d");if(!ctx)throw Error("Preview pixel access unavailable");
      ctx.drawImage(v,0,0,canvas.width,canvas.height);
      const p=suggestCameraLayout(ctx.getImageData(0,0,canvas.width,canvas.height),s.count,[v.videoWidth,v.videoHeight],arrangement);p.preview_time_s=v.currentTime;
      s.setProposal(p);s.setCameras(c=>c.map((row,i)=>i<s.count?{...row,crop:p.rectangles[i]}:row));s.setCropsConfirmed(false);setSuggestionError("");
    }catch {setSuggestionError("Automatic suggestion unavailable. Use equal panels or edit the regions in this preview; no external cropping is needed.");}
  };
  useEffect(()=>{
    if(lastFile.current!==s.files[0]){lastSuggestion.current="";lastFile.current=s.files[0];}
    const key=`${s.files[0]?.name}/${s.files[0]?.lastModified}/${s.files[0]?.size}/${s.count}/${arrangement}`;
    const v=video.current;
    if(s.sourceMode!=="composite"||!s.ready[0]||!v?.readyState||lastSuggestion.current===key)return;
    let done=false;
    const run=()=>{if(done)return;done=true;lastSuggestion.current=key;suggest();};
    // loadeddata can precede the first composited video frame in Chromium.
    const frame=v.requestVideoFrameCallback?.(run),timer=window.setTimeout(run,200);
    return()=>{done=true;window.clearTimeout(timer);if(frame!=null)v.cancelVideoFrameCallback?.(frame);};
  },[s.files,s.count,s.sourceMode,s.ready,arrangement]);
  const markReady=(i:number)=>s.setReady(v=>{const next=[...v];next[i]=true;return next;});
  return <fieldset disabled={disabled} className="space-y-3"><legend>Camera setup</legend>
    <label>Camera count <select aria-label="Camera count" value={s.count} onChange={e=>s.setCount(Number(e.target.value))}>{[1,2,3].map(n=><option key={n} value={n}>{n}</option>)}</select></label>{" "}
    <label>Source layout <select aria-label="Source layout" value={s.sourceMode} onChange={e=>s.setSourceMode(e.target.value)}><option value="separate">{s.count===1?"One camera recording":"Separate synchronized camera MP4s"}</option><option value="composite">Fixed-panel composite MP4</option></select></label>
    {s.cameraSet&&<>
      <p>Camera-local image-space evidence only. No cross-view identity or calibrated 3D; the combined task outcome remains uncertain.</p>
      {s.sourceMode==="composite"&&<>
        <label>Composite MP4 <input type="file" accept="video/mp4,.mp4" aria-label="Composite MP4" onChange={e=>s.chooseFile(0,e.target.files?.[0])}/></label>
        <div className="multicamera-crop-preview"><Preview file={s.files[0]} videoRef={video} onReady={()=>markReady(0)} onSize={(w,h)=>s.setSize([w,h])}/>
          {s.size[0]>0&&<div className="crop-boundaries" aria-label="Pixel crop preview">{s.cameras.slice(0,s.count).map((c,i)=><div key={i} style={{left:`${100*c.crop[0]/s.size[0]}%`,top:`${100*c.crop[1]/s.size[1]}%`,width:`${100*c.crop[2]/s.size[0]}%`,height:`${100*c.crop[3]/s.size[1]}%`}}>{c.name}</div>)}</div>}
        </div>
        <p>Native source: {s.size.join(" × ")} px. Crop extraction preserves source frames and presentation timestamps.</p>
        <label>Suggested arrangement <select aria-label="Suggested arrangement" value={arrangement} onChange={e=>setArrangement(e.target.value as typeof arrangement)}><option value="auto">Automatic suggestion</option><option value="horizontal">Side by side</option><option value="vertical">Stacked</option></select></label>{" "}
        <Button disabled={!s.ready[0]} onClick={suggest}>Suggest camera regions</Button>
        {s.proposal&&<p role="status">{s.proposal.note}</p>}{suggestionError&&<p>{suggestionError}</p>}
        <Button disabled={!s.size[0]} onClick={()=>s.setCameras(v=>v.map((c,i)=>({...c,crop:[Math.floor(i*s.size[0]/s.count/2)*2,0,Math.floor(s.size[0]/s.count/2)*2,Math.floor(s.size[1]/2)*2]})))}>Set equal horizontal panels</Button>{" "}
        {s.size[0]===3872&&s.size[1]===736&&s.count===3&&<Button onClick={()=>s.setCameras(v=>v.map((c,i)=>({...c,crop:[8+1288*i,8,1280,720]})))}>Preview DROID panel boundaries</Button>}
      </>}
      <div className="multicamera-configs">{s.cameras.slice(0,s.count).map((c,i)=><fieldset key={i}><legend>cam{i+1}</legend>
        <label>Name <input aria-label={`Camera ${i+1} name`} value={c.name} onChange={e=>s.change(i,"name",e.target.value)}/></label>
        {s.sourceMode==="separate"&&<><label>MP4 <input type="file" accept="video/mp4,.mp4" aria-label={`Camera ${i+1} MP4`} onChange={e=>s.chooseFile(i,e.target.files?.[0])}/></label><Preview file={s.files[i]} onReady={()=>markReady(i)}/></>}
        <label>Object prompt <input aria-label={`Camera ${i+1} object prompt`} value={c.object_concept} onChange={e=>s.change(i,"object_concept",e.target.value)}/></label>
        <label>Destination prompt <input aria-label={`Camera ${i+1} destination prompt`} value={c.destination_concept} onChange={e=>s.change(i,"destination_concept",e.target.value)}/></label>
        <label>Camera motion <select aria-label={`Camera ${i+1} motion`} value={c.motion} onChange={e=>s.change(i,"motion",e.target.value as Camera["motion"])}><option value="unknown">Unknown</option><option value="static">Stationary</option><option value="moving">Moving / wrist camera</option></select></label>
        {s.sourceMode==="composite"?<div>{["x","y","width","height"].map((key,k)=><label key={key}>{key}<input type="number" step="2" min="0" aria-label={`Camera ${i+1} crop ${key}`} value={c.crop[k]} onChange={e=>s.change(i,"crop",c.crop.map((n,j)=>j===k?Number(e.target.value):n))}/></label>)}</div>:<label>Source offset (s) <input type="number" step="0.01" aria-label={`Camera ${i+1} offset`} value={c.offset_s} onChange={e=>s.change(i,"offset_s",Number(e.target.value))}/></label>}
      </fieldset>)}</div>
      {s.sourceMode==="composite"?<label><input type="checkbox" aria-label="Confirm crop boundaries" checked={s.cropsConfirmed} onChange={e=>s.setCropsConfirmed(e.target.checked)}/> I inspected and confirm every fixed crop boundary.</label>:s.count>1&&<>
        <p>Source elapsed time = shared time + offset. Equal offsets do not prove synchronization.</p>
        <label>Alignment basis <input aria-label="Alignment basis" value={s.basis} onChange={e=>s.setBasis(e.target.value)}/></label>
        <label><input type="checkbox" aria-label="Approve camera alignment" checked={s.aligned} onChange={e=>s.setAligned(e.target.checked)}/> I approve the stated alignment and camera offsets.</label>
      </>}
    </>}
  </fieldset>;
}
