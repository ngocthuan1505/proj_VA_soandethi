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
 assert.equal(tasks.size,24,'Expected three tasks per member');
 for(const role of roles)assert.equal(plan.tasks.filter(t=>t.role===role).length,3,'Three tasks required: '+role);
 for(const t of tasks.values()){
  assert(roles.includes(t.role)&&t.id.startsWith(t.role+'-'),'Invalid role/task ID');
  assert(milestones.has(t.milestone)&&['P0','P1'].includes(t.priority));
  assert(t.title&&t.files?.length&&t.acceptance?.length>=3&&t.tests,'Missing acceptance/validation');
  assert(t.execution?.inputs&&t.execution.deliverables&&t.execution.pattern&&t.execution.steps?.length>=3,'Missing task execution details');
  assert(t.execution.reviewers?.length&&t.execution.reviewers.every(r=>roles.includes(r)&&r!==t.role),'Invalid reviewer role');
  assert(t.execution.courseTasks?.length&&t.execution.courseTasks.every(id=>/^CT-0[1-6]$/.test(id)),'Invalid course evidence reference');
  for(const dep of t.dependsOn)assert(tasks.has(dep)&&dep!==t.id,'Invalid dependency '+dep);
 }
 const done=new Set(),visiting=new Set();
 function visit(id){assert(!visiting.has(id),'Dependency cycle at '+id);if(done.has(id))return;visiting.add(id);for(const dep of tasks.get(id).dependsOn)visit(dep);visiting.delete(id);done.add(id);}
 for(const id of tasks.keys())visit(id);
 return plan;
}
export function executionSection(task){
 if(!task.execution)return '';
 const e=task.execution;
 return `<!-- mach-course-execution:${task.id} -->\n## Bắt tay thực hiện và bằng chứng môn\n\n**Đầu vào:** ${e.inputs}\n\n**Đầu ra:** ${e.deliverables}\n\n**Pattern/công cụ:** ${e.pattern}\n\n### Các bước nhỏ\n\n${e.steps.map((s,i)=>'- [ ] '+(i+1)+'. '+s).join('\n')}\n\nĐây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.\n\n**Reviewer theo vai trò:** ${e.reviewers.join(', ')}; chờ username thực, không tự gán người chưa biết.\n\n**Hồ sơ môn liên quan:** ${e.courseTasks.join(', ')} — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).\n\n[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.\n<!-- /mach-course-execution:${task.id} -->\n`;
}
export function issueBody(task,roster,mapping={}){
 const dep=id=>mapping[id]?'#'+mapping[id].number:id;
 return `<!-- mach-team:${task.id} -->\n## Phân công\n\n- Vai trò: **${task.role}**\n- Thành viên: ${roster[task.role]?'@'+roster[task.role]:'Chưa có username; nhận theo vai trò.'}\n- Milestone: ${task.milestone}; ưu tiên: ${task.priority}\n- Phụ thuộc: ${task.dependsOn.length?task.dependsOn.map(dep).join(', '):'Không — có thể bắt đầu ngay.'}\n\n## Phạm vi source\n\n${task.files.map(f=>'- `'+f+'`').join('\n')}\n\n## Tiêu chí nghiệm thu\n\n${task.acceptance.map(a=>'- [ ] '+a).join('\n')}\n\n## Kiểm tra\n\n${task.tests}\n\nĐọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.\n\n`+executionSection(task);
}
export function backlogMarkdown(plan,roster,mapping={}){
 let text='# Backlog nhóm — 24 task\n\nNguồn duy nhất: [tasks.json](tasks.json); danh sách thành viên: [roster.json](roster.json). Các task là việc cần làm, không phải chức năng đã hoàn thành. Mốc không có deadline cho đến khi nhóm chốt.\n\n';
 text+='**Demo để kế thừa:** [Chức năng và phần còn thiếu](../product/DEMO_DA_CO.md) · [Cách mở app và test](CHAY_VA_TEST_DEMO.md) · [Baseline thực chạy](../testing/BASELINE_2026_11_05.md). Đọc trước khi nhận task; demo Node không thay nghiệm thu Python.\n\n';
 text+='**Bảng công việc:** [Bảng tiến độ kéo thả](https://github.com/users/ngocthuan1505/projects/1/views/1) · [Danh sách công việc](https://github.com/users/ngocthuan1505/projects/1/views/2) · [Hướng dẫn cập nhật và thông báo](BOARD.md) · [Các mốc](https://github.com/'+plan.repository+'/milestones)\n\nTrạng thái hiện tại xem ở trường Status trên Project riêng tư; mỗi thẻ là issue gốc. Nhãn issue `status:*` không tự đồng bộ với bảng. Chi tiết kế hoạch dưới đây không phải báo cáo việc đã hoàn thành.\n\n';
 for(const m of plan.milestones){
  text+='## '+m.title+'\n\n'+m.description+'\n\n| Task | Vai trò / thành viên | Đầu ra | Phụ thuộc |\n|---|---|---|---|\n';
  for(const t of plan.tasks.filter(t=>t.milestone===m.id))text+='| '+(mapping[t.id]?'['+t.id+']('+mapping[t.id].url+')':t.id)+' | '+t.role+(roster[t.role]?' / @'+roster[t.role]:' / chờ username')+' | '+t.title+' | '+(t.dependsOn.join(', ')||'Bắt đầu ngay')+' |\n';
  text+='\n';
 }
 text+='## Chi tiết nghiệm thu\n\n';
 for(const t of plan.tasks)text+='### '+t.id+' — '+t.title+'\n\n'+issueBody(t,roster,mapping).replace(/<!--.*?-->\n/,'')+'\n';
 return text.trimEnd()+'\n';
}
