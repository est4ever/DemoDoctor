import { useEffect, useRef, useState } from "react";
import { Button } from "./ui";
import { suggestCameraLayout, type LayoutProposal } from "../lib/cameraLayout";

type NumericEdit = number | string;
type Camera = {name:string;motion:"unknown"|"static"|"moving";offset_s:NumericEdit;object_concept:string;destination_concept:string;crop:NumericEdit[]};
const camera=(i:number):Camera=>({name:`Camera ${i+1}`,motion:"unknown",offset_s:0,object_concept:"green plate",destination_concept:"dish rack",crop:[0,0,640,480]});
export type CameraInputDraft = {count:number;sourceMode:string;cameras:Camera[];files:Array<File|undefined>;size:[number,number];cropsConfirmed:boolean;aligned:boolean;basis:string;proposal:LayoutProposal|null};
export type CameraInputError = {field:string;message:string};
const numeric = (value:NumericEdit) => String(value).trim() !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
const cameraField = (i:number,key:string) => `camera-${i}-${key}`;

/** Input state only. Preparation, payment approval, progress and recovery share LiveAnalyzePanel. */
export function useCameraInputs(initial?:CameraInputDraft) {
  const [count,setCount]=useState(initial?.count??1),[sourceMode,setSourceMode]=useState(initial?.sourceMode??"separate");
  const [cameras,setCameras]=useState(initial?.cameras??[camera(0),camera(1),camera(2)]);
  const [files,setFiles]=useState<Array<File|undefined>>(initial?.files??[]),[ready,setReady]=useState<boolean[]>([]);
  const [size,setSize]=useState<[number,number]>(initial?.size??[0,0]),[cropsConfirmed,setCropsConfirmed]=useState(initial?.cropsConfirmed??false);
  const [aligned,setAligned]=useState(initial?.aligned??false),[basis,setBasis]=useState(initial?.basis??"");
  const [proposal,setProposal]=useState<LayoutProposal|null>(initial?.proposal??null);
  const [durations,setDurations]=useState<number[]>([]);
  const previous=useRef({count,sourceMode,cameras,files});
  useEffect(()=>{
    const p=previous.current;
    if(p.count!==count||p.sourceMode!==sourceMode||p.cameras!==cameras||p.files!==files){setCropsConfirmed(false);setAligned(false);}
    if(p.sourceMode!==sourceMode){setFiles([]);setReady([]);setSize([0,0]);setProposal(null);setDurations([]);}
    previous.current={count,sourceMode,cameras,files};
  },[count,sourceMode,cameras,files]);
  const cameraSet=count>1||sourceMode==="composite";
  const chooseFile=(i:number,file?:File)=>{setFiles(v=>{const next=[...v];next[i]=file;return next;});setReady(v=>{const next=[...v];next[i]=false;return next;});setDurations(v=>{const next=[...v];next[i]=0;return next;});if(sourceMode==="composite"){setSize([0,0]);setProposal(null);}};
  const change=(i:number,key:keyof Camera,value:Camera[keyof Camera])=>setCameras(v=>v.map((c,j)=>j===i?{...c,[key]:value}:c));
  const selected=sourceMode==="composite"?[files[0]]:Array.from({length:count},(_,i)=>files[i]);
  const previewReady=selected.every((f,i)=>f&&ready[i]);
  const validate=(start=0,end?:number):CameraInputError|null=>{
    const fail=(field:string,message:string)=>({field,message});
    if(![1,2,3].includes(count))return fail('camera-count','Choose one, two or three camera views.');
    if(!['separate','composite'].includes(sourceMode))return fail('camera-layout','Choose separate recordings or a fixed-panel composite.');
    for(let i=0;i<selected.length;i++){
      const f=selected[i],field=sourceMode==='composite'?'camera-composite':cameraField(i,'file');
      if(!f||!f.size||!f.name.toLowerCase().endsWith('.mp4'))return fail(field,'Choose a non-empty MP4 for every selected source.');
      if(!ready[i])return fail(field,`Preview source ${i+1} before preparation; choose a decodable MP4.`);
    }
    if(sourceMode==='composite'&&!size[0])return fail('camera-composite','Inspect the native source preview and confirm every crop boundary before preparation.');
    const names=new Set<string>();
    for(let i=0;i<count;i++){
      const c=cameras[i];
      for(const key of ['name','object_concept','destination_concept'] as const){
        if(!c[key].trim())return fail(cameraField(i,key),`Enter Camera ${i+1}'s ${key==='name'?'name':key==='object_concept'?'object prompt':'destination prompt'}.`);
      }
      if(names.has(c.name.trim().toLowerCase()))return fail(cameraField(i,'name'),'Use a distinct name for each camera.');
      names.add(c.name.trim().toLowerCase());
      if(sourceMode==='separate'){
        const offset=numeric(c.offset_s);
        if(offset===null||Math.abs(offset)>60)return fail(cameraField(i,'offset'),`Enter Camera ${i+1}'s offset from −60 to 60 seconds. Use 0 explicitly only if aligned.`);
      }else{
        for(let k=0;k<4;k++){
          const n=numeric(c.crop[k]);
          if(n===null||!Number.isInteger(n)||n%2!==0||n<(k<2?0:16))return fail(cameraField(i,`crop-${k}`),'Enter even pixel crop coordinates; x/y must be non-negative and width/height at least 16.');
        }
        const [x,y,w,h]=c.crop.map(Number);
        if(x+w>size[0])return fail(cameraField(i,'crop-2'),'Crop width extends beyond the original video.');
        if(y+h>size[1])return fail(cameraField(i,'crop-3'),'Crop height extends beyond the original video.');
        for(let j=0;j<i;j++){
          const [bx,by,bw,bh]=cameras[j].crop.map(Number);
          if(Math.max(x,bx)<Math.min(x+w,bx+bw)&&Math.max(y,by)<Math.min(y+h,by+bh))return fail(cameraField(i,'crop-0'),'Camera crop regions must not overlap.');
        }
      }
    }
    if(sourceMode==='composite'&&(!size[0]||!cropsConfirmed))return fail('camera-crops','Inspect and confirm every crop boundary before preparation.');
    if(sourceMode==='separate'&&count>1&&!aligned)return fail('camera-aligned','Approve the per-camera offsets and describe the alignment basis.');
    if(sourceMode==='separate'&&count>1&&basis.trim().length<8)return fail('camera-basis','Describe the alignment basis in at least 8 characters; equal offsets alone do not establish synchronization.');
    if(durations.slice(0,selected.length).length===selected.length&&durations.slice(0,selected.length).every(d=>d>0)){
      const offsets=sourceMode==='composite'?[0]:cameras.slice(0,count).map(c=>Number(c.offset_s));
      const sharedStart=Math.max(0,...offsets.map(n=>-n)),sharedEnd=Math.min(...durations.slice(0,selected.length).map((d,i)=>d-offsets[i]));
      if(sharedEnd<=sharedStart)return fail(sourceMode==='composite'?'camera-composite':cameraField(0,'offset'),'The source times do not overlap. Correct the offsets or choose synchronized recordings.');
      if(end!==undefined&&(end>sharedEnd-sharedStart||start<0))return fail('window-end','The selected shared window extends beyond the overlapping source footage. Choose an earlier end time.');
    }
    return null;
  };
  const form=(task:string,start:number,end:number,dry:boolean,questions="")=>{
    const problem=validate();if(problem)throw new Error(problem.message);
    const data=new FormData();selected.forEach(f=>data.append("videos",f!));data.append("dry_run",String(dry));
    data.append("manifest",JSON.stringify({source_mode:sourceMode,task_description:task,
      cameras:cameras.slice(0,count).map(c=>({...c,crop:sourceMode==="composite"?c.crop.map(Number):null,offset_s:sourceMode==="composite"?0:Number(c.offset_s)})),
      alignment_confirmed:aligned,alignment_basis:basis,crops_confirmed:cropsConfirmed,layout_proposal:proposal,investigation_questions:questions,window_start_s:start,window_end_s:end}));
    return data;
  };
  const draft={count,sourceMode,cameras,files,size,cropsConfirmed,aligned,basis,proposal};
  const dirty=count!==1||sourceMode!=='separate'||files.some(Boolean)||basis!==''||JSON.stringify(cameras)!==JSON.stringify([camera(0),camera(1),camera(2)]);
  return {count,setCount,sourceMode,setSourceMode,cameras,setCameras,files,chooseFile,change,ready,setReady,size,setSize,cropsConfirmed,setCropsConfirmed,aligned,setAligned,basis,setBasis,proposal,setProposal,cameraSet,previewReady,validate,form,draft,dirty,setDurations,restored:!!initial};
}
type Setup=ReturnType<typeof useCameraInputs>;

function Preview({file,onReady,onSize,onDuration,videoRef}:{file?:File;onReady:()=>void;onSize?:(w:number,h:number)=>void;onDuration?:(duration:number)=>void;videoRef?:React.RefObject<HTMLVideoElement|null>}) {
  const [src,setSrc]=useState<string>();
  useEffect(()=>{if(!file){setSrc(undefined);return;}const url=URL.createObjectURL(file);setSrc(url);return()=>URL.revokeObjectURL(url);},[file]);
  return src?<video ref={videoRef} src={src} controls muted playsInline style={{width:"100%",maxHeight:220,objectFit:"contain"}} onLoadedData={onReady} onLoadedMetadata={e=>{onSize?.(e.currentTarget.videoWidth,e.currentTarget.videoHeight);onDuration?.(e.currentTarget.duration);}}/>:null;
}

export function CameraInputs({setup:s,disabled,error,onEdit,announcementKey}:{setup:Setup;disabled:boolean;error?:CameraInputError|null;onEdit?:()=>void;announcementKey?:number}) {
  const attributes=(field:string)=>({id:`analysis-${field}`,'aria-invalid':error?.field===field||undefined,'aria-describedby':error?.field===field?'analysis-input-error':undefined});
  const inline=(field:string)=>error?.field===field?<small key={announcementKey} id="analysis-input-error" role="alert" className="text-[var(--danger)]">{error.message}</small>:null;
  const duration=(i:number,value:number)=>s.setDurations(v=>{const next=[...v];next[i]=value;return next;});
  const video=useRef<HTMLVideoElement>(null),lastSuggestion=useRef(s.restored?`${s.files[0]?.name}/${s.files[0]?.lastModified}/${s.files[0]?.size}/${s.count}/auto`:""),lastFile=useRef<File|undefined>(s.files[0]);
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
  return <fieldset disabled={disabled} className="space-y-3" onChange={onEdit}><legend>Camera setup</legend>
    <label>Camera count <select {...attributes('camera-count')} aria-label="Camera count" value={s.count} onChange={e=>s.setCount(Number(e.target.value))}>{[1,2,3].map(n=><option key={n} value={n}>{n}</option>)}</select>{inline('camera-count')}</label>{" "}
    <label>Source layout <select {...attributes('camera-layout')} aria-label="Source layout" value={s.sourceMode} onChange={e=>s.setSourceMode(e.target.value)}><option value="separate">{s.count===1?"One camera recording":"Separate synchronized camera MP4s"}</option><option value="composite">Fixed-panel composite MP4</option></select>{inline('camera-layout')}</label>
    {s.cameraSet&&<>
      <p>Camera-local image-space evidence only. No cross-view identity or calibrated 3D; the combined task outcome remains uncertain.</p>
      {s.sourceMode==="composite"&&<>
        <label>Composite MP4 <input {...attributes('camera-composite')} type="file" accept="video/mp4,.mp4" aria-label="Composite MP4" onChange={e=>s.chooseFile(0,e.target.files?.[0])}/>{s.files[0]&&<small>Selected: {s.files[0].name}</small>}{inline('camera-composite')}</label>
        <div className="multicamera-crop-preview"><Preview file={s.files[0]} videoRef={video} onReady={()=>markReady(0)} onSize={(w,h)=>s.setSize([w,h])} onDuration={d=>duration(0,d)}/>
          {s.size[0]>0&&<div className="crop-boundaries" aria-label="Pixel crop preview">{s.cameras.slice(0,s.count).map((c,i)=>c.crop.every(n=>numeric(n)!==null)?<div key={i} style={{left:`${100*Number(c.crop[0])/s.size[0]}%`,top:`${100*Number(c.crop[1])/s.size[1]}%`,width:`${100*Number(c.crop[2])/s.size[0]}%`,height:`${100*Number(c.crop[3])/s.size[1]}%`}}>{c.name}</div>:null)}</div>}
        </div>
        <p>Native source: {s.size.join(" × ")} px. Crop extraction preserves source frames and presentation timestamps.</p>
        <label>Suggested arrangement <select aria-label="Suggested arrangement" value={arrangement} onChange={e=>setArrangement(e.target.value as typeof arrangement)}><option value="auto">Automatic suggestion</option><option value="horizontal">Side by side</option><option value="vertical">Stacked</option></select></label>{" "}
        <Button disabled={!s.ready[0]} onClick={suggest}>Suggest camera regions</Button>
        {s.proposal&&<p role="status">{s.proposal.note}</p>}{suggestionError&&<p>{suggestionError}</p>}
        <Button disabled={!s.size[0]} onClick={()=>s.setCameras(v=>v.map((c,i)=>({...c,crop:[Math.floor(i*s.size[0]/s.count/2)*2,0,Math.floor(s.size[0]/s.count/2)*2,Math.floor(s.size[1]/2)*2]})))}>Set equal horizontal panels</Button>{" "}
        {s.size[0]===3872&&s.size[1]===736&&s.count===3&&<Button onClick={()=>s.setCameras(v=>v.map((c,i)=>({...c,crop:[8+1288*i,8,1280,720]})))}>Preview DROID panel boundaries</Button>}
      </>}
      <div className="multicamera-configs">{s.cameras.slice(0,s.count).map((c,i)=><fieldset key={i}><legend>cam{i+1}</legend>
        <label>Name <input {...attributes(cameraField(i,'name'))} aria-label={`Camera ${i+1} name`} value={c.name} onChange={e=>s.change(i,"name",e.target.value)}/>{inline(cameraField(i,'name'))}</label>
        {s.sourceMode==="separate"&&<><label>MP4 <input {...attributes(cameraField(i,'file'))} type="file" accept="video/mp4,.mp4" aria-label={`Camera ${i+1} MP4`} onChange={e=>s.chooseFile(i,e.target.files?.[0])}/>{s.files[i]&&<small>Selected: {s.files[i]?.name}</small>}{inline(cameraField(i,'file'))}</label><Preview file={s.files[i]} onReady={()=>markReady(i)} onDuration={d=>duration(i,d)}/></>}
        <label>Object prompt <input {...attributes(cameraField(i,'object_concept'))} aria-label={`Camera ${i+1} object prompt`} value={c.object_concept} onChange={e=>s.change(i,"object_concept",e.target.value)}/>{inline(cameraField(i,'object_concept'))}</label>
        <label>Destination prompt <input {...attributes(cameraField(i,'destination_concept'))} aria-label={`Camera ${i+1} destination prompt`} value={c.destination_concept} onChange={e=>s.change(i,"destination_concept",e.target.value)}/>{inline(cameraField(i,'destination_concept'))}</label>
        <label>Camera motion <select aria-label={`Camera ${i+1} motion`} value={c.motion} onChange={e=>s.change(i,"motion",e.target.value as Camera["motion"])}><option value="unknown">Unknown</option><option value="static">Stationary</option><option value="moving">Moving / wrist camera</option></select></label>
        {s.sourceMode==="composite"?<div>{["x","y","width","height"].map((key,k)=><label key={key}>{key}<input {...attributes(cameraField(i,`crop-${k}`))} type="number" step="2" min={k<2?0:16} aria-label={`Camera ${i+1} crop ${key}`} value={c.crop[k]} onChange={e=>s.change(i,"crop",c.crop.map((n,j)=>j===k?e.target.value:n))}/>{inline(cameraField(i,`crop-${k}`))}</label>)}</div>:<label>Source offset (s) <input {...attributes(cameraField(i,'offset'))} type="number" step="0.01" min="-60" max="60" aria-label={`Camera ${i+1} offset`} value={c.offset_s} onChange={e=>s.change(i,"offset_s",e.target.value)}/>{inline(cameraField(i,'offset'))}</label>}
      </fieldset>)}</div>
      {s.sourceMode==="composite"?<label><input {...attributes('camera-crops')} type="checkbox" aria-label="Confirm crop boundaries" checked={s.cropsConfirmed} onChange={e=>s.setCropsConfirmed(e.target.checked)}/> I inspected and confirm every fixed crop boundary.{inline('camera-crops')}</label>:s.count>1&&<>
        <p>Source elapsed time = shared time + offset. Equal offsets do not prove synchronization.</p>
        <label>Alignment basis <input {...attributes('camera-basis')} aria-label="Alignment basis" value={s.basis} onChange={e=>s.setBasis(e.target.value)}/>{inline('camera-basis')}</label>
        <label><input {...attributes('camera-aligned')} type="checkbox" aria-label="Approve camera alignment" checked={s.aligned} onChange={e=>s.setAligned(e.target.checked)}/> I approve the stated alignment and camera offsets.{inline('camera-aligned')}</label>
      </>}
    </>}
  </fieldset>;
}
