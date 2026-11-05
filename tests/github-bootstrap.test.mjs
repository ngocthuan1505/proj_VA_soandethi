import test from 'node:test';import assert from 'node:assert/strict';import {readFile} from 'node:fs/promises';
import {syncGitHub} from '../scripts/bootstrap-github.mjs';
const plan=JSON.parse(await readFile(new URL('../docs/team/tasks.json',import.meta.url),'utf8'));
const roster=JSON.parse(await readFile(new URL('../docs/team/roster.json',import.meta.url),'utf8'));
function fixture(privateRepo=true){
 const state={labels:[],milestones:[],issues:[],writes:0};
 const api=async(method,path,body)=>{
  if(method==='GET'){
   if(path==='')return {private:privateRepo,permissions:{admin:true}};
   if(path.startsWith('/labels?'))return state.labels;
   if(path.startsWith('/milestones?'))return state.milestones;
   if(path.startsWith('/issues?'))return state.issues;
  }
  state.writes++;
  if(method==='POST'&&path==='/labels'){state.labels.push(body);return body;}
  if(method==='POST'&&path==='/milestones'){const value={...body,number:state.milestones.length+1,state:'open',html_url:'https://example.test/milestone'};state.milestones.push(value);return value;}
  if(method==='PATCH'&&path.startsWith('/milestones/')){const m=state.milestones.find(x=>x.number===Number(path.split('/')[2]));Object.assign(m,body);return m;}
  if(method==='POST'&&path==='/issues'){const value={...body,number:state.issues.length+1,html_url:'https://example.test/issues/'+(state.issues.length+1),state:'open',assignees:(body.assignees||[]).map(login=>({login}))};state.issues.push(value);return value;}
  const number=Number(path.split('/')[2]),issue=state.issues.find(i=>i.number===number);assert(issue,'Unknown issue');
  if(method==='PATCH'){Object.assign(issue,body);return issue;}
  if(method==='POST'&&path.endsWith('/assignees')){issue.assignees=body.assignees.map(login=>({login}));return issue;}
  throw Error('Unexpected '+method+' '+path);
 };
 return {api,state};
}
test('Bootstrap creates 24 linked tasks, three milestones and tracker once; re-run preserves human edits/status',async()=>{
 const f=fixture();const result=await syncGitHub(f.api,plan,roster);assert.equal(result.createdTasks,24);assert.equal(f.state.issues.length,25);assert.equal(f.state.milestones.length,3);
 assert.equal(f.state.issues.filter(i=>i.labels.includes('status:ready')).length,8);
 const task=f.state.issues.find(i=>i.body.includes('<!-- mach-team:UI-1-002 -->'));assert(task.body.includes('#1'));task.body+='\nHUMAN NOTE';task.labels=['status:doing'];
 const writes=f.state.writes;const again=await syncGitHub(f.api,plan,roster);assert.equal(again.createdTasks,0);assert.equal(f.state.writes,writes);assert(task.body.endsWith('HUMAN NOTE'));assert.deepEqual(task.labels,['status:doing']);
});
test('Bootstrap refuses public repository before any write and never assigns invented usernames',async()=>{
 const f=fixture(false);await assert.rejects(()=>syncGitHub(f.api,plan,roster),/Private/);assert.equal(f.state.writes,0);
 const g=fixture();await syncGitHub(g.api,plan,roster);assert(g.state.issues.filter(i=>i.assignees.length).every(i=>Object.values(roster).includes(i.assignees[0].login)));
});
test('Roster không tự gán việc: giữ assignee tự chọn, nhiều người và issue chưa nhận',async()=>{
 const chosen={...roster,'UI-1':'new-teammate'};const f=fixture();await syncGitHub(f.api,plan,chosen);
 assert(f.state.issues.filter(i=>/mach-team:(?:UI|BE)-/.test(i.body)).every(i=>i.assignees.length===0));
 const first=f.state.issues[0];first.assignees=[{login:'volunteer-a'},{login:'volunteer-b'}];const last=f.state.issues.find(i=>i.body.includes('<!-- mach-team:UI-1-003 -->'));last.state='closed';
 const writes=f.state.writes;await syncGitHub(f.api,plan,chosen);assert.equal(f.state.writes,writes);assert.deepEqual(first.assignees.map(a=>a.login),['volunteer-a','volunteer-b']);
 assert.equal(last.assignees.length,0);assert.equal(f.state.issues.find(i=>i.body.includes('<!-- mach-team:UI-1-002 -->')).assignees.length,0);
});
test('Explicit plan refresh updates only untouched generated task bodies; human changes are reported and preserved',async()=>{
 const f=fixture();await syncGitHub(f.api,plan,roster);const changed=structuredClone(plan);changed.tasks[0].title+=' updated';changed.tasks[0].acceptance.push('Additional Python criterion');changed.tasks[1].acceptance.push('Another criterion');const human=f.state.issues[1];human.body+='\nHUMAN CHANGE';const result=await syncGitHub(f.api,changed,roster,{previousPlan:plan});assert(f.state.issues[0].title.endsWith('updated'));assert(human.body.endsWith('HUMAN CHANGE'));assert(result.skippedEditedTasks.includes(plan.tasks[1].id));assert.equal(f.state.issues.length,25);
});
