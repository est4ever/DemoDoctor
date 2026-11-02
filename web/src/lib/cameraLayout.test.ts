import { expect,it } from "vitest";
import { suggestCameraLayout } from "./cameraLayout";

function panels(count:number,vertical=false,panelWidth=60){
  const step=panelWidth+4,width=step*count+8,height=68,w=vertical?height:width,h=vertical?width:height,data=new Uint8ClampedArray(w*h*4);
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
    const major=vertical?y:x,cross=vertical?x:y;
    const panel=Math.floor((major-4)/step),local=(major-4)%step;
    if(panel>=0&&panel<count&&local>=0&&local<panelWidth&&cross>=4&&cross<64){const k=(y*w+x)*4;data[k]=140;data[k+1]=80;data[k+2]=100;data[k+3]=255;}
  }
  return{width:w,height:h,data};
}
it.each([2,3])("suggests %i side-by-side views from actual gutters, not robot labels",count=>{
  const image=panels(count),r=suggestCameraLayout(image,count,[image.width,image.height]);
  expect(r.method).toBe("dark-gutters");expect(r.axis).toBe("horizontal");expect(r.rectangles).toHaveLength(count);
  expect(r.rectangles.map(x=>x[0])).toEqual(Array.from({length:count},(_,i)=>4+64*i));
  expect(r.rectangles.every(x=>x[2]===60)).toBe(true);expect(r.note).toContain("unverified");
});
it("suggests stacked panels and falls back explicitly when no reliable separators exist",()=>{
  const image=panels(2,true),r=suggestCameraLayout(image,2,[image.width,image.height]);
  expect(r.axis).toBe("vertical");expect(r.method).toBe("dark-gutters");
  const uniform={width:192,height:64,data:new Uint8ClampedArray(192*64*4).fill(120)};
  const fallback=suggestCameraLayout(uniform,3,[192,64]);
  expect(fallback.method).toBe("equal-panels");expect(fallback.rectangles).toEqual([[0,0,64,64],[64,0,64,64],[128,0,64,64]]);
  expect(fallback.note).toContain("No reliable");
});
it("does not discard an entire dark scene edge joined to a narrow separator",()=>{
  const image=panels(3,false,600);
  for(let x=588;x<604;x++)for(let y=0;y<image.height;y++){const i=(y*image.width+x)*4;image.data[i]=image.data[i+1]=image.data[i+2]=0;}
  const p=suggestCameraLayout(image,3,[image.width,image.height]);
  expect(p.rectangles[0][2]).toBe(600);expect(p.rectangles[1][0]).toBe(608);
});
