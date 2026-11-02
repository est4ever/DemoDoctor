export type LayoutProposal = {method:"dark-gutters"|"equal-panels";axis:"horizontal"|"vertical";rectangles:number[][];preview_time_s:number;note:string};

/** Pixel-layout heuristic only. It never identifies objects, outcomes or camera identity. */
export function suggestCameraLayout(image: Pick<ImageData,"width"|"height"|"data">, count:number, original:[number,number], axis:"auto"|"horizontal"|"vertical"="auto"):LayoutProposal {
  if(![1,2,3].includes(count))throw Error("Select one to three camera regions");
  const {width:w,height:h,data}=image;
  const profile=(vertical:boolean)=>Array.from({length:vertical?w:h},(_,i)=>{
    const length=vertical?h:w;let dark=0,n=0;
    for(let j=2;j<length-2;j+=Math.max(1,Math.floor(length/512))){const x=vertical?i:j,y=vertical?j:i,k=(y*w+x)*4;n++;if(data[k]<28&&data[k+1]<28&&data[k+2]<28)dark++;}
    return n?dark/n:0;
  });
  const columns=profile(true),rows=profile(false);
  const bands=(p:number[])=>{const out:Array<[number,number]>=[];for(let i=0;i<p.length;){if(p[i]<.97){i++;continue;}const a=i;while(i<p.length&&p[i]>=.97)i++;out.push([a,i]);}return out;};
  const edge=(p:number[],reverse=false)=>{let n=0;while(n<p.length*.1&&p[reverse?p.length-1-n:n]>=.97)n++;return n;};
  const seams=(p:number[])=>Array.from({length:count-1},(_,i)=>{
    const expected=p.length*(i+1)/count;
    return bands(p).filter(([a,b])=>a>p.length*.04&&b<p.length*.96&&b-a<=p.length*.04&&Math.abs((a+b)/2-expected)<p.length*.09)
      .sort((a,b)=>Math.abs((a[0]+a[1])/2-expected)-Math.abs((b[0]+b[1])/2-expected))[0];
  });
  const cx=seams(columns),cy=seams(rows);
  const chosen=axis!=="auto"?axis:cx.every(Boolean)&&count>1?"horizontal":cy.every(Boolean)&&count>1?"vertical":original[0]>=original[1]?"horizontal":"vertical";
  const p=chosen==="horizontal"?columns:rows,found=chosen==="horizontal"?cx:cy;
  const gutters=count>1&&found.every(Boolean);
  const start=edge(p),finish=p.length-edge(p,true);
  const narrow=Math.min(...found.filter(Boolean).map(b=>b![1]-b![0]),...(start>0?[start]:[]),...(finish<p.length?[p.length-finish]:[]));
  // A dark scene edge can join a gutter. Only exceptionally wide bands use the
  // narrowest visible border as a geometric suggestion; the operator must confirm.
  const seamStart=(index:number)=>{const b=found[index]!;return b[1]-b[0]>4*narrow?b[1]-narrow:b[0];};
  const cross=chosen==="horizontal"?rows:columns,top=gutters?edge(cross):0,bottom=gutters?cross.length-edge(cross,true):cross.length;
  const scaleX=original[0]/w,scaleY=original[1]/h;
  const even=(v:number)=>Math.max(0,Math.round(v/2)*2);
  const rectangles=Array.from({length:count},(_,i)=>{
    const a=gutters?(i===0?start:found[i-1]![1]):p.length*i/count;
    const b=gutters?(i===count-1?finish:seamStart(i)):p.length*(i+1)/count;
    const x=chosen==="horizontal"?a:top,y=chosen==="horizontal"?top:a;
    const right=chosen==="horizontal"?b:bottom,lower=chosen==="horizontal"?bottom:b;
    const ex=even(x*scaleX),ey=even(y*scaleY),er=Math.min(original[0]-original[0]%2,even(right*scaleX)),eb=Math.min(original[1]-original[1]%2,even(lower*scaleY));
    return[ex,ey,Math.max(0,er-ex),Math.max(0,eb-ey)];
  });
  return {method:gutters?"dark-gutters":"equal-panels",axis:chosen,rectangles,preview_time_s:0,
    note:gutters?"Suggested from dark separators in this preview frame. Regions are unverified until you inspect and confirm them.":"No reliable separator set found; equal panels are only a layout suggestion. Inspect or edit every region before confirmation."};
}
