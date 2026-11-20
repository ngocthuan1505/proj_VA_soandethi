export function documentPages(doc) {
 return doc.pages?.length ? doc.pages : [{number:1,text:doc.text}];
}

export function selectedDocumentPages(exam, doc) {
 const selected=exam.assistantSourcePages?.[doc.id];
 return documentPages(doc).filter(page=>!Array.isArray(selected)||selected.includes(page.number));
}

export function sourcePageLabel(doc, pageNumber) {
 if(doc.personalLesson&&pageNumber===1&&doc.sourceLocator)return doc.sourceLocator;
 if(doc.kind==='slides')return 'Slide '+pageNumber;
 return doc.catalog ? 'Bài ' + pageNumber : 'Trang ' + pageNumber;
}
