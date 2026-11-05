import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateTaskDetail,validateCourseDetails,taskDetailSection,appendTaskDetails} from '../scripts/team-plan.mjs';
const plan=JSON.parse(await readFile(new URL('../docs/team/tasks.json',import.meta.url),'utf8'));
const course=JSON.parse(await readFile(new URL('../docs/course/deliverables.json',import.meta.url),'utf8'));

test('Chặn checklist trùng ID, thiếu expected result hoặc bàn giao sai vai trò trước đồng bộ',()=>{
 const task=plan.tasks[0];validateTaskDetail(task);
 let bad=structuredClone(task);bad.detail.work[1].id=bad.detail.work[0].id;assert.throws(()=>validateTaskDetail(bad),/Duplicate work/);
 bad=structuredClone(task);delete bad.detail.cases[0].expected;assert.throws(()=>validateTaskDetail(bad),/expected/);
 bad=structuredClone(task);bad.detail.handoff.to=['unknown-role'];assert.throws(()=>validateTaskDetail(bad),/handoff/);
 bad=structuredClone(task);bad.detail.cases=bad.detail.cases.filter(c=>c.kind!=='error');assert.throws(()=>validateTaskDetail(bad),/negative/);
 bad=structuredClone(task);bad.detail.useCases=['UC-99'];assert.throws(()=>validateTaskDetail(bad),/use case/);
});

test('Bổ sung chi tiết giữ nguyên checklist/note cũ, chạy lại không thêm bản trùng',()=>{
 const task=plan.tasks[0],before='<!-- mach-team:'+task.id+' -->\n- [x] Công việc người dùng đã kiểm\nGhi chú riêng\n';
 const result=appendTaskDetails(before,task);assert.equal(result.status,'appended');assert(result.body.startsWith(before));
 assert(result.body.includes('W01'));assert(result.body.includes('T01'));assert(result.body.includes('Kết quả phải chứng minh'));
 assert.deepEqual(appendTaskDetails(result.body,task),{body:result.body,status:'unchanged'});
});

test('Phần chi tiết bị người dùng sửa/tick hoặc marker thiếu không bị ghi đè',()=>{
 const task=plan.tasks[1],edited=taskDetailSection(task).replace('- [ ] **W01**','- [x] **W01**')+'\nGhi chú người review';
 assert.deepEqual(appendTaskDetails(edited,task),{body:edited,status:'preserved-human-edit'});
 const partial='<!-- mach-task-detail:'+task.id+' -->\nChưa hoàn thiện';assert.equal(appendTaskDetails(partial,task).status,'preserved-human-edit');
});

test('Sáu hồ sơ và các tham chiếu yêu cầu/use case hợp lệ; phát hiện vòng phụ thuộc',()=>{
 validateCourseDetails(course);const bad=structuredClone(course);bad[0].dependsOn=['CT-06'];assert.throws(()=>validateCourseDetails(bad),/cycle/);
 const all=[...plan.tasks,...course];assert.equal(all.length,30);
 assert.equal(new Set(all.flatMap(t=>t.detail.requirements)).size,8);assert.equal(new Set(all.flatMap(t=>t.detail.useCases)).size,11);
 for(const task of all)validateTaskDetail(task);
});
