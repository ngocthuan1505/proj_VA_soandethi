// Small, consistent outline icons for application actions.
const paths={
 file:'M6 3h8l4 4v14H6zM14 3v5h5M9 12h6M9 16h6',
 edit:'m15 4 5 5M4 20l4-1L20 7l-3-3L5 16z',
 view:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
 insert:'M12 4v16M4 12h16',format:'M4 5h16M12 5v15M8 20h8',
 tools:'M14 5a5 5 0 0 0-6 6L3 16a3 3 0 0 0 5 5l5-5a5 5 0 0 0 6-6l-4 2-3-3z',
 share:'M16 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6M6 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6M17 16a3 3 0 1 0 0 6 3 3 0 0 0 0-6M8.5 10.5l5-3M8.5 13.5l5.5 4',
 sparkle:'m12 3 2.6 6.4L21 12l-6.4 2.6L12 21l-2.6-6.4L3 12l6.4-2.6z',
 folder:'M3 6h7l2 3h9v12H3z',upload:'M12 16V3M7 8l5-5 5 5M4 16v5h16v-5',
 download:'M12 3v13M7 11l5 5 5-5M4 17v4h16v-4',
 undo:'M8 4 3 9l5 5M3 9h10a7 7 0 0 1 0 14',redo:'m16 4 5 5-5 5M21 9H11a7 7 0 0 0 0 14',
 history:'M3 4v6h6M3 10a9 9 0 1 1 1 9M12 7v5l3 2',
 table:'M3 4h18v16H3zM3 10h18M10 4v16',image:'M3 4h18v16H3zM3 16l5-5 4 4 3-3 6 6M8 8h.1',
 check:'m4 12 5 5L20 6',book:'M3 4h6q3 0 3 3 0-3 3-3h6v16h-6q-3 0-3 2 0-2-3-2H3zM12 7v15',
 align:'M4 5h16M4 10h11M4 15h16M4 20h11',list:'M8 5h13M8 12h13M8 19h13M3 5h.1M3 12h.1M3 19h.1',
 settings:'M4 6h16M4 12h16M4 18h16M8 3v6M16 9v6M10 15v6',
 link:'M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71',
 arrow:'M5 12h14m-5-5 5 5-5 5',chat:'M3 4h18v13H8l-5 4zM7 8h10M7 12h7',
 layout:'M3 4h18v16H3zM9 4v16',quote:'M4 6h6v7H6q0 3-3 4M14 6h6v7h-4q0 3-3 4'
};
const actions={new:'insert',generate:'sparkle',library:'folder','import-doc':'upload',export:'download','backup-local':'download','import-backup':'upload',replace:'edit','question-meta':'settings','view-student':'file','view-teacher':'check',matrix:'table','toggle-ai':'chat','scroll-marking':'list','add-question':'insert','add-essay':'edit',formula:'sparkle',chemistry:'tools','insert-image':'image',geometry:'tools','insert-table':'table','page-break':'layout','align-left':'align','align-center':'align','align-justify':'align','bullet-list':'list','number-list':'list',metadata:'file',layout:'layout','check-all':'check','ai-check':'sparkle',quotes:'quote',extract:'file',memory:'book',connections:'settings','studio-table':'table','studio-sketch':'edit','studio-question':'insert','studio-paragraph':'align','studio-layout':'layout','studio-link':'link','studio-rule':'align','studio-add-question':'insert'};
export function uiIcon(name){return `<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${paths[actions[name]||name]||paths.file}"/></svg>`;}
