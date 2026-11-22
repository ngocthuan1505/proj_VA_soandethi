// Ngắt trang là thuộc tính của khối đầu trang, vẫn lưu chung trong bodyTextDoc.
export function splitDocumentPages(doc){
 const pages=[{type:'doc',content:[]}];
 for(const node of doc?.content||[]){
  if(node.attrs?.pageBreakBefore&&pages.at(-1).content.length)pages.push({type:'doc',content:[]});
  pages.at(-1).content.push(structuredClone(node));
 }
 return pages;
}
export function joinDocumentPages(pages){
 return {type:'doc',content:pages.flatMap((page,index)=>{
  const nodes=structuredClone(page.content?.length?page.content:[{type:'paragraph'}]);
  nodes.forEach((node,i)=>{if(node.attrs?.pageBreakBefore)delete node.attrs.pageBreakBefore;if(i===0&&index>0)node.attrs={...node.attrs,pageBreakBefore:true};});
  return nodes;
 })};
}
