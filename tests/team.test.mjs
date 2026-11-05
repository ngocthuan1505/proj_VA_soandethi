import test from 'node:test';import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validatePlan,issueBody} from '../scripts/team-plan.mjs';
const plan=JSON.parse(await readFile(new URL('../docs/team/tasks.json',import.meta.url),'utf8'));
const roster=JSON.parse(await readFile(new URL('../docs/team/roster.json',import.meta.url),'utf8'));
test('Team plan covers exactly 3 UI and 5 backend roles, including owner, with a dependency DAG',()=>{assert.equal(validatePlan(plan,roster).tasks.length,24);});
test('Missing dependencies and cycles are rejected before GitHub mutations',()=>{let bad=structuredClone(plan);bad.tasks[0].dependsOn=['NO-SUCH-TASK'];assert.throws(()=>validatePlan(bad,roster),/Invalid dependency/);bad=structuredClone(plan);bad.tasks[0].dependsOn=['UI-1-002'];assert.throws(()=>validatePlan(bad,roster),/cycle/);});
test('Owner and identity validation prevents accidental reassignment or invalid handles',()=>{assert.throws(()=>validatePlan(plan,{...roster,'BE-1':null}),/Thuận/);assert.throws(()=>validatePlan(plan,{...roster,'UI-1':'not a username'}),/username/);assert.throws(()=>validatePlan(plan,{...roster,'UI-1':'ngocthuan1505'}),/two roles/);});
test('Course constraint cannot silently revert to a Node-primary architecture',()=>{assert.throws(()=>validatePlan({...plan,architecture:{primaryLanguage:'Node'}},roster),/Python/);assert(plan.tasks.filter(t=>t.role.startsWith('BE')).every(t=>t.acceptance.some(a=>a.includes('Python là backend/core chính'))));});
test('Issue bodies preserve stable IDs, criteria and resolve dependency links without invented assignees',()=>{const t=plan.tasks.find(t=>t.id==='UI-1-002');const body=issueBody(t,roster,{'UI-1-001':{number:7}});assert(body.includes('<!-- mach-team:UI-1-002 -->'));assert(body.includes('#7'));assert(body.includes('BE-2-001'));assert(body.includes('@'+roster['UI-1']));const unknown=issueBody(t,{...roster,'UI-1':null});assert(unknown.includes('Chưa có username'));assert(body.includes('- [ ]'));assert(!unknown.includes('@null'));});
test('Task hướng dẫn phải có bước làm, reviewer hợp lệ và hồ sơ CT để thành viên bắt đầu',()=>{
 const bad=structuredClone(plan);delete bad.tasks[0].execution;assert.throws(()=>validatePlan(bad,roster),/execution/);
 const same=structuredClone(plan);same.tasks[0].execution.reviewers=['UI-1'];assert.throws(()=>validatePlan(same,roster),/reviewer/);
 const wrong=structuredClone(plan);wrong.tasks[0].execution.courseTasks=['CT-99'];assert.throws(()=>validatePlan(wrong,roster),/evidence/);
 const body=issueBody(plan.tasks[0],roster);assert(body.includes('mach-course-execution:UI-1-001'));assert(body.includes('Đầu vào'));assert(body.includes('Các bước nhỏ'));assert(body.includes('CT-01'));assert(body.includes('BAO_CAO.md'));
});
