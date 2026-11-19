export function documentPages(doc) {
 return doc.pages?.length ? doc.pages : [{number:1,text:doc.text}];
}

export function selectedDocumentPages(exam, doc) {
 const selected=exam.assistantSourcePages?.[doc.id];
 return documentPages(doc).filter(page=>!Array.isArray(selected)||selected.includes(page.number));
}
