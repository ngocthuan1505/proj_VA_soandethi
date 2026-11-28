import katex from './katex/katex.mjs';
import './katex/contrib/mhchem.mjs';
import {renderFigure} from '../geometry.js';
import {dataChartSVG} from '../core.js';

// Chỉ trình bày dữ liệu do Python chọn; không gọi mạng hoặc dịch vụ AI.
export async function renderExportAssets(input){
 const math={};for(const latex of input.math||[]){
  const template=document.createElement('template');
  template.innerHTML=katex.renderToString(latex,{output:'mathml',throwOnError:true,trust:false,strict:'ignore',maxExpand:1000,maxSize:40});
  math[latex]=new XMLSerializer().serializeToString(template.content.querySelector('math'));
 }
 const figures=[];for(const spec of input.figures||[]){
  const raw=spec.dataChart?dataChartSVG(spec.dataChart):renderFigure(spec),box=raw.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/),svg=raw.replace('<svg ',`<svg width="${box[1]}" height="${box[2]}" `),url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml'}));
  try{
   const image=new Image();image.src=url;await image.decode();
   const canvas=document.createElement('canvas');canvas.width=960;canvas.height=Math.ceil(960*image.height/image.width);
   if(!canvas.height||canvas.height>1600)throw Error('Kích thước hình chưa hợp lệ.');
   canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);figures.push({svg,png:canvas.toDataURL('image/png')});
  }finally{URL.revokeObjectURL(url);}
 }
 return {math,figures};
}
