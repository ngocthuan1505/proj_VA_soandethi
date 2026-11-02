// Explicit repository administration only; dry-run by default, never deploys an app.
import {readFile,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {fileURLToPath,pathToFileURL} from 'node:url';
import path from 'node:path';
import assert from 'node:assert/strict';
import {validatePlan,issueBody,backlogMarkdown,roles} from './team-plan.mjs';

const root=fileURLToPath(new URL('../',import.meta.url));
const areaFor=role=>role.startsWith('UI')?'ui':({'BE-1':'ai','BE-2':'api','BE-3':'database','BE-4':'documents','BE-5':'qa'}[role]);
export async function syncGitHub(api,plan,roster,{previousPlan}={}){
 validatePlan(plan,roster);
 const repo=await api('GET','');assert(repo.private===true,'Repository must stay Private');assert(repo.permissions?.admin,'Repository admin permission required');
 const labels=[...roles.map(name=>({name:'role:'+name,color:name.startsWith('UI')?'1D76DB':'0E8A16'})),...['ready','doing','review','blocked'].map(name=>({name:'status:'+name,color:name==='blocked'?'B60205':'D4C5F9'})),...['task','bug','tracker'].map(name=>({name:'type:'+name,color:'FBCA04'})),...['P0','P1'].map(name=>({name:'priority:'+name,color:name==='P0'?'D93F0B':'FEF2C0'})),...['ui','ai','api','database','documents','qa'].map(name=>({name:'area:'+name,color:'C2E0C6'}))];
 const existingLabels=await api('GET','/labels?per_page=100');
 for(const label of labels)if(!existingLabels.some(x=>x.name===label.name))await api('POST','/labels',label);
 const existingMilestones=await api('GET','/milestones?state=all&per_page=100'),milestones={};
 for(const m of plan.milestones){const existing=existingMilestones.find(x=>x.title===m.title);milestones[m.id]=existing||await api('POST','/milestones',{title:m.title,description:m.description});assert(milestones[m.id].state!=='closed','Milestone already closed; do not silently reopen');}
 const issues=[];
 for(let page=1;page<=20;page++){const part=await api('GET','/issues?state=all&per_page=100&page='+page);issues.push(...part.filter(x=>!x.pull_request));if(part.length<100)break;assert(page<20,'Too many issues; narrow sync before continuing');}
 const mapping={},created=[],refreshed=[],skippedEdits=[];
 for(const task of plan.tasks){
  const marker='<!-- mach-team:'+task.id+' -->';
  const matches=issues.filter(i=>i.body?.includes(marker));assert(matches.length<=1,'Duplicate remote task marker '+task.id);
  let issue=matches[0];
  if(!issue){
   const assignees=roster[task.role]?[roster[task.role]]:[];
   issue=await api('POST','/issues',{title:'['+task.id+'] '+task.title,body:issueBody(task,roster),milestone:milestones[task.milestone].number,labels:['type:task','role:'+task.role,'area:'+areaFor(task.role),'priority:'+task.priority,'status:'+(task.dependsOn.length?'blocked':'ready')],assignees});created.push(task.id);
  }else if(roster[task.role]&&!issue.assignees?.length&&issue.state!=='closed'){
   await api('POST','/issues/'+issue.number+'/assignees',{assignees:[roster[task.role]]});
  }
  mapping[task.id]={number:issue.number,url:issue.html_url};
 }
 if(previousPlan){
  for(const task of plan.tasks){
   if(created.includes(task.id))continue;
   const remote=issues.find(i=>i.number===mapping[task.id].number),old=previousPlan.tasks.find(t=>t.id===task.id);
   assert(old&&remote,'Missing task baseline for refresh');
   const before=issueBody(old,roster,mapping).replace(/\r\n/g,'\n');
   if(remote.body?.replace(/\r\n/g,'\n')===before){
    await api('PATCH','/issues/'+remote.number,{title:'['+task.id+'] '+task.title,body:issueBody(task,roster,mapping)});refreshed.push(task.id);
   }else if(remote.body?.replace(/\r\n/g,'\n')!==issueBody(task,roster,mapping))skippedEdits.push(task.id);
  }
  for(const m of plan.milestones)await api('PATCH','/milestones/'+milestones[m.id].number,{description:m.description});
 }
 // Update only bodies just created in this run; preserve edits/checklists on existing issues.
 for(const id of created){const task=plan.tasks.find(t=>t.id===id);await api('PATCH','/issues/'+mapping[id].number,{body:issueBody(task,roster,mapping)});}
 const marker='<!-- mach-team:TRACKER -->';let tracker=issues.find(i=>i.body?.includes(marker));
 if(!tracker){
  let body=marker+'\n# Kế hoạch đồ án — 3 UI + 5 backend\n\nBE-1 là @ngocthuan1505, duy nhất vận hành GreenNode. Các vai trò khác chờ username; phân công qua nhãn role. Đọc [hướng dẫn nhóm](https://github.com/'+plan.repository+'/blob/main/docs/team/README.md). Không đăng URL/token server.\n\n';
  for(const m of plan.milestones){body+='## '+m.title+'\n\n';for(const t of plan.tasks.filter(t=>t.milestone===m.id))body+='- [ ] #'+mapping[t.id].number+' — '+t.id+'\n';body+='\n';}
  body+='Bắt đầu task 001. Sau khi phụ thuộc xong, chuyển task blocked sang ready. Một status mỗi issue. Chưa mời thành viên khi chưa có username; chưa đặt deadline hoặc bật auto-deploy.';
  tracker=await api('POST','/issues',{title:'Kế hoạch nhóm: 3 UI + 5 backend, GreenNode chỉ Thuận',body,labels:['type:tracker'],assignees:['ngocthuan1505']});
 }
 if(plan.architecture?.primaryLanguage==='Python'&&!tracker.body?.includes('<!-- python-primary -->')){
  await api('PATCH','/issues/'+tracker.number,{body:tracker.body+'\n\n<!-- python-primary -->\n**Cập nhật quy định môn học: Python/FastAPI là backend và core chính; JavaScript hỗ trợ UI. Task đã đổi hướng triển khai Python. Xem [kế hoạch chuyển đổi](https://github.com/'+plan.repository+'/blob/main/docs/architecture/PYTHON_MIGRATION.md). Node backend chỉ legacy reference, không proxy core để thay Python.**'});
 }
 const final=await api('GET','');assert(final.private===true);
 return {mapping,tracker:{number:tracker.number,url:tracker.html_url},createdTasks:created.length,refreshedTasks:refreshed.length,skippedEditedTasks:skippedEdits,milestones:Object.fromEntries(Object.entries(milestones).map(([id,m])=>[id,{number:m.number,url:m.html_url}]))};
}

async function main(){
 const plan=JSON.parse(await readFile(path.join(root,'docs/team/tasks.json'),'utf8')),roster=JSON.parse(await readFile(path.join(root,'docs/team/roster.json'),'utf8'));validatePlan(plan,roster);
 if(!process.argv.includes('--apply')){console.log(JSON.stringify({dryRun:true,repository:plan.repository,privateRequired:true,tasks:plan.tasks.length,roles:roles.length,milestones:plan.milestones.length,knownAssignees:Object.values(roster).filter(Boolean),serverOperations:false}));return;}
 let token=process.env.GITHUB_TOKEN||'';
 if(!token){
  let raw;try{raw=execFileSync('git',['credential-manager','get'],{input:'protocol=https\nhost=github.com\nusername=ngocthuan1505\n\n',encoding:'utf8',stdio:['pipe','pipe','pipe'],env:{...process.env,GCM_INTERACTIVE:'never',GIT_TERMINAL_PROMPT:'0'},timeout:20000});}catch{throw Error('GitHub credential unavailable; sign in through normal GitHub/Git flow, do not paste a token into chat.');}
  const fields=Object.fromEntries(raw.trim().split(/\r?\n/).map(line=>{const i=line.indexOf('=');return [line.slice(0,i),line.slice(i+1)];}));token=fields.password;
 }
 assert(token,'No GitHub credential');
 try{
  async function api(method,suffix,body){
   const r=await fetch('https://api.github.com/repos/'+plan.repository+suffix,{method,headers:{Accept:'application/vnd.github+json',Authorization:'Bearer '+token,'Content-Type':'application/json','User-Agent':'Mach-team-setup'},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(20000)});
   if(!r.ok)throw Error('GitHub '+method+' '+suffix+' returned '+r.status+'; earlier successful operations are retained, rerun safely after resolving permission/rate limits.');
   return r.status===204?null:r.json();
  }
  const refreshIndex=process.argv.indexOf('--refresh-from');
  const previousPlan=refreshIndex>=0?JSON.parse(await readFile(path.resolve(process.argv[refreshIndex+1]),'utf8')):undefined;
  const result=await syncGitHub(api,plan,roster,{previousPlan});
  await writeFile(path.join(root,'docs/team/github-issues.json'),JSON.stringify(result.mapping,null,2)+'\n');
  await writeFile(path.join(root,'docs/team/BACKLOG.md'),backlogMarkdown(plan,roster,result.mapping));
  await writeFile(path.join(root,'docs/team/github-setup.json'),JSON.stringify({...result,mapping:undefined,repository:plan.repository,private:true},null,2)+'\n');
  console.log(JSON.stringify({private:true,createdTasks:result.createdTasks,refreshedTasks:result.refreshedTasks,skippedEditedTasks:result.skippedEditedTasks,totalTasks:Object.keys(result.mapping).length,tracker:result.tracker,milestones:result.milestones,credentialsSaved:false,serverOperations:false}));
 }finally{token='';}
}
if(process.argv[1]&&import.meta.url===pathToFileURL(path.resolve(process.argv[1])).href)main().catch(error=>{console.error(error.message);process.exitCode=1;});
