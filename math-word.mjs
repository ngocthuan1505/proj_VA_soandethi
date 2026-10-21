import katex from './assets/katex/katex.mjs';
import './assets/katex/contrib/mhchem.mjs';
import {dependency} from './runtime.mjs';
// Extra notation passes through the same mathematical parser used by preview.
// Emit editable OMML, excluding KaTeX's source annotation from the document.
export function extendedMathNodes(d,latex){
 const source=katex.renderToString(latex,{output:'mathml',displayMode:true,throwOnError:true,trust:false,strict:'ignore'}),tree=dependency('xml-js').xml2js(source,{compact:false});
 const component=(name,children=[])=>{const n=new d.XmlComponent('m:'+name);for(const child of children)n.addChildElement(child);return n;};
 const prop=(name,value)=>{const n=component(name);n.addChildElement(new d.XmlAttributeComponent({'m:val':value}));return n;};
 const elements=n=>(n.elements||[]).filter(x=>x.type==='element'),nodes=n=>convert(n),all=n=>(n.elements||[]).flatMap(convert),text=n=>n.type==='text'?n.text:(n.elements||[]).map(text).join('');
 function convert(n){if(n.type==='text')return n.text?[new d.MathRun(n.text)]:[];if(n.type!=='element')return [];const c=elements(n);switch(n.name){
  case 'annotation':case 'annotation-xml':case 'mphantom':return [];
  case 'mspace':return [new d.MathRun(' ')];
  case 'mi':case 'mn':case 'mo':case 'mtext':return [new d.MathRun(text(n))];
  case 'msup':return [new d.MathSuperScript({children:nodes(c[0]),superScript:nodes(c[1])})];
  case 'msub':return [new d.MathSubScript({children:nodes(c[0]),subScript:nodes(c[1])})];
  case 'msubsup':return [new d.MathSubSuperScript({children:nodes(c[0]),subScript:nodes(c[1]),superScript:nodes(c[2])})];
  case 'msqrt':return [new d.MathRadical({children:all(n)})];
  case 'mroot':return [new d.MathRadical({children:nodes(c[0]),degree:nodes(c[1])})];
  case 'mfrac':{if(n.attributes?.linethickness==='0px'){const f=component('f',[component('fPr',[prop('type','noBar')]),component('num',nodes(c[0])),component('den',nodes(c[1]))]);return [f];}return [new d.MathFraction({numerator:nodes(c[0]),denominator:nodes(c[1])})];}
  case 'mtable':return [component('m',c.map(row=>component('mr',elements(row).map(cell=>component('e',all(cell))))))];
  case 'mover':{const chr=text(c[1]);if(['→','¯','^','ˆ','˙','¨','⏞'].includes(chr))return [component('acc',[component('accPr',[prop('chr',chr)]),component('e',nodes(c[0]))])];return [component('limUpp',[component('e',nodes(c[0])),component('lim',nodes(c[1]))])];}
  case 'munder':return [component('limLow',[component('e',nodes(c[0])),component('lim',nodes(c[1]))])];
  case 'munderover':return [component('limUpp',[component('e',[component('limLow',[component('e',nodes(c[0])),component('lim',nodes(c[1]))])]),component('lim',nodes(c[2]))])];
  default:return all(n);
 }}
 return (tree.elements||[]).flatMap(convert);
}
export function needsExtendedMath(latex){return /\\(?:binom|underbrace|mid|lVert|rVert|longrightarrow|lfloor|rfloor)\b|\\begin\{vmatrix\}|\\ce\{[^}]*\{|.+\\begin\{/.test(latex);}
