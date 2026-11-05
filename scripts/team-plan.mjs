import assert from 'node:assert/strict';
export const roles=['UI-1','UI-2','UI-3','BE-1','BE-2','BE-3','BE-4','BE-5'];
export function validatePlan(plan,roster){
 assert.equal(plan.repository,'ngocthuan1505/proj_VA_soandethi','Wrong repository');
 assert.equal(plan.architecture?.primaryLanguage,'Python','Course requires Python as the primary language');
 assert.deepEqual(Object.keys(roster).sort(),[...roles].sort(),'Roster must have exactly 8 roles');
 assert.equal(roster['BE-1'],'ngocthuan1505','Only Thuận operates GreenNode');
 for(const username of Object.values(roster))assert(username===null||/^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$/i.test(username),'Invalid GitHub username');
 const assigned=Object.values(roster).filter(Boolean);assert.equal(new Set(assigned).size,assigned.length,'One member cannot occupy two roles');
 const milestones=new Set(plan.milestones.map(m=>m.id));assert.equal(milestones.size,3);
 const tasks=new Map(plan.tasks.map(t=>[t.id,t]));assert.equal(tasks.size,plan.tasks.length,'Duplicate task ID');
 assert.equal(tasks.size,24,'Expected three phases per work area');
 for(const role of roles)assert.equal(plan.tasks.filter(t=>t.role===role).length,3,'Three phase tasks required for area: '+role);
 for(const t of tasks.values()){
  assert(roles.includes(t.role)&&t.id.startsWith(t.role+'-'),'Invalid role/task ID');
  assert(milestones.has(t.milestone)&&['P0','P1'].includes(t.priority));
  assert(t.title&&t.files?.length&&t.acceptance?.length>=3&&t.tests,'Missing acceptance/validation');
  assert(t.execution?.inputs&&t.execution.deliverables&&t.execution.pattern&&t.execution.steps?.length>=3,'Missing task execution details');
  assert(t.execution.reviewers?.length&&t.execution.reviewers.every(r=>roles.includes(r)&&r!==t.role),'Invalid reviewer role');
  assert(t.execution.courseTasks?.length&&t.execution.courseTasks.every(id=>/^CT-0[1-6]$/.test(id)),'Invalid course evidence reference');
  validateTaskDetail(t);
  for(const dep of t.dependsOn)assert(tasks.has(dep)&&dep!==t.id,'Invalid dependency '+dep);
 }
 const done=new Set(),visiting=new Set();
 function visit(id){assert(!visiting.has(id),'Dependency cycle at '+id);if(done.has(id))return;visiting.add(id);for(const dep of tasks.get(id).dependsOn)visit(dep);visiting.delete(id);done.add(id);}
 for(const id of tasks.keys())visit(id);
 return plan;
}
export function validateTaskDetail(task){
 const d=task.detail;
 assert(d?.ready&&d.work?.length>=4,'Missing detailed work: '+task.id);
 assert.equal(new Set(d.work.map(w=>w.id)).size,d.work.length,'Duplicate work ID');
 assert(d.work.every(w=>/^W\d{2}$/.test(w.id)&&w.text?.trim()),'Invalid work item');
 assert(d.handoff?.artifact&&d.handoff.to?.length&&d.handoff.to.every(r=>roles.includes(r)&&r!==task.role),'Invalid handoff role');
 assert(d.cases?.length>=3&&['happy','error','edge'].every(k=>d.cases.some(c=>c.kind===k)),'Missing expected/negative/boundary cases');
 assert.equal(new Set(d.cases.map(c=>c.id)).size,d.cases.length,'Duplicate case ID');
 assert(d.cases.every(c=>/^T\d{2}$/.test(c.id)&&c.action&&c.expected),'Missing test expected result');
 assert(d.requirements?.length&&d.requirements.every(r=>/^R[1-8]$/.test(r)),'Invalid requirement reference');
 assert(d.useCases?.length&&d.useCases.every(u=>/^UC-(?:0[1-9]|1[01])$/.test(u)),'Invalid use case reference');
 return d;
}
export function taskDetailSection(task){
 if(!task.detail)return '';
 const d=validateTaskDetail(task),cell=s=>s.replaceAll('|','\\|').replaceAll('\n','<br>');
 return `<!-- mach-task-detail:${task.id} -->\n## Chỉ dẫn chi tiết và bàn giao\n\n**Điều kiện bắt đầu:** ${d.ready}\n\n### Việc nhỏ có thể nhận và review\n\n${d.work.map(w=>'- [ ] **'+w.id+'** — '+w.text).join('\n')}\n\nMã bước/ca luôn đi cùng task, ví dụ ${task.id}/W01 và ${task.id}/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.\n\n### Ca kiểm tra và kết quả mong đợi\n\n| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |\n|---|---|---|---|\n${d.cases.map(c=>'| '+c.id+' | '+({happy:'Đúng',error:'Lỗi/từ chối',edge:'Biên/đồng thời'}[c.kind]||c.kind)+' | '+cell(c.action)+' | '+cell(c.expected)+' |').join('\n')}\n\nĐây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.\n\n**Đầu ra cụ thể:** ${d.handoff.artifact}\n\n**Mảng cần bàn giao:** ${d.handoff.to.join(', ')}. Nhóm chọn người/nhóm nhận bàn giao và xác nhận contract dùng được; không suy username từ mã mảng. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.\n\n**Truy vết:** ${d.requirements.join(', ')}; ${d.useCases.join(', ')}. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).\n\nAcceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.\n<!-- /mach-task-detail:${task.id} -->\n`;
}
export function appendTaskDetails(body,task){
 const section=taskDetailSection(task);assert(section,'Task detail required');
 if(body.includes(section))return {body,status:'unchanged'};
 if(body.includes('<!-- mach-task-detail:'+task.id+' -->'))return {body,status:'preserved-human-edit'};
 return {body:body+'\n\n'+section,status:'appended'};
}
export function validateCourseDetails(course){
 assert.equal(course.length,6,'Expected six course tasks');
 const tasks=new Map(course.map(t=>[t.id,t]));assert.equal(tasks.size,6,'Duplicate course ID');
 for(const t of course){
  assert(/^CT-0[1-6]$/.test(t.id)&&roles.includes(t.role),'Invalid course task');validateTaskDetail(t);
  assert(t.dependsOn.every(id=>tasks.has(id)&&id!==t.id),'Invalid course dependency');
 }
 const done=new Set(),visiting=new Set();
 function visit(id){assert(!visiting.has(id),'Course dependency cycle');if(done.has(id))return;visiting.add(id);for(const dep of tasks.get(id).dependsOn)visit(dep);visiting.delete(id);done.add(id);}
 for(const id of tasks.keys())visit(id);
 return course;
}
export function courseBacklogMarkdown(course,mapping={}){
 return '# Chi tiết sáu task hồ sơ môn\n\nDùng lại [hồ sơ đã có](HO_SO_DA_CO.md). Đây là bước cần làm tiếp, không đặt lại tiến độ/assignee hoặc coi hồ sơ đã làm là chưa có. Nguồn: deliverables.json; sinh bằng node scripts/check-team.mjs --write.\n\n'+course.map(t=>'## '+t.id+' — '+t.title+'\n\n'+(mapping[t.id]?'[Issue #'+mapping[t.id].number+']('+mapping[t.id].url+') · ':'')+'Mảng điều phối gợi ý (nhóm tự chọn người): '+t.role+'; phối hợp theo contract: '+t.collaborators.join(', ')+'. Phụ thuộc hồ sơ: '+(t.dependsOn.join(', ')||'Không')+'.\n\n[Hồ sơ làm việc]('+t.document+') · [Phần đã có](HO_SO_DA_CO.md)\n\n### Acceptance giữ nguyên\n\n'+t.criteria.map(s=>'- [ ] '+s).join('\n')+'\n\n'+taskDetailSection(t)).join('\n');
}
export function executionSection(task){
 if(!task.execution)return '';
 const e=task.execution;
 return `<!-- mach-course-execution:${task.id} -->\n## Bắt tay thực hiện và bằng chứng môn\n\n**Đầu vào:** ${e.inputs}\n\n**Đầu ra:** ${e.deliverables}\n\n**Pattern/công cụ:** ${e.pattern}\n\n### Các bước nhỏ\n\n${e.steps.map((s,i)=>'- [ ] '+(i+1)+'. '+s).join('\n')}\n\nĐây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.\n\n**Reviewer theo vai trò:** ${e.reviewers.join(', ')}; đây là mảng cần tham khảo; chọn người review khác người thực hiện, không suy username từ mã.\n\n**Hồ sơ môn liên quan:** ${e.courseTasks.join(', ')} — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).\n\n[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.\n<!-- /mach-course-execution:${task.id} -->\n`;
}
export function issueBody(task,roster,mapping={}){
 const dep=id=>mapping[id]?'#'+mapping[id].number:id;
 return `<!-- mach-team:${task.id} -->\n## Mảng việc để tự chọn\n\n- Mảng: **${task.role}** (mã chuyên môn, không phải người).\n- Người thực hiện: Chưa đăng ký; có thể nhận cá nhân hoặc nhóm. Xem [cách chọn việc](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/CHON_VIEC.md).\n- Milestone: ${task.milestone}; ưu tiên: ${task.priority}\n- Phụ thuộc: ${task.dependsOn.length?task.dependsOn.map(dep).join(', '):'Không — có thể bắt đầu ngay.'}\n\n## Phạm vi source\n\n${task.files.map(f=>'- `'+f+'`').join('\n')}\n\n## Tiêu chí nghiệm thu\n\n${task.acceptance.map(a=>'- [ ] '+a).join('\n')}\n\n## Kiểm tra\n\n${task.tests}\n\nĐọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.\n\n`+executionSection(task)+taskDetailSection(task);
}
export function backlogMarkdown(plan,roster,mapping={}){
 let text='# Backlog nhóm — 24 task\n\nNguồn duy nhất: [tasks.json](tasks.json); danh sách nhóm: [members.json](members.json); [tự chọn cá nhân hoặc làm chung](CHON_VIEC.md). Các task là việc cần làm, không phải chức năng đã hoàn thành. Mốc không có deadline cho đến khi nhóm chốt.\n\n';
 text+='**Demo để kế thừa:** [Chức năng và phần còn thiếu](../product/DEMO_DA_CO.md) · [Cách mở app và test](CHAY_VA_TEST_DEMO.md) · [Baseline thực chạy](../testing/BASELINE_2026_11_05.md). Đọc trước khi nhận task; demo Node không thay nghiệm thu Python.\n\n';
 text+='**Bảng công việc:** [Bảng tiến độ kéo thả](https://github.com/users/ngocthuan1505/projects/1/views/1) · [Danh sách công việc](https://github.com/users/ngocthuan1505/projects/1/views/2) · [Hướng dẫn cập nhật và thông báo](BOARD.md) · [Các mốc](https://github.com/'+plan.repository+'/milestones)\n\nTrạng thái hiện tại xem ở trường Status trên Project riêng tư; mỗi thẻ là issue gốc. Nhãn issue `status:*` không tự đồng bộ với bảng. Chi tiết kế hoạch dưới đây không phải báo cáo việc đã hoàn thành.\n\n';
 for(const m of plan.milestones){
  text+='## '+m.title+'\n\n'+m.description+'\n\n| Task | Mảng / cách nhận | Đầu ra | Phụ thuộc |\n|---|---|---|---|\n';
  for(const t of plan.tasks.filter(t=>t.milestone===m.id))text+='| '+(mapping[t.id]?'['+t.id+']('+mapping[t.id].url+')':t.id)+' | '+t.role+' / tự chọn hoặc làm chung'+' | '+t.title+' | '+(t.dependsOn.join(', ')||'Bắt đầu ngay')+' |\n';
  text+='\n';
 }
 text+='## Chi tiết nghiệm thu\n\n';
 for(const t of plan.tasks)text+='### '+t.id+' — '+t.title+'\n\n'+issueBody(t,roster,mapping).replace(/<!--.*?-->\n/,'')+'\n';
 return text.trimEnd()+'\n';
}
