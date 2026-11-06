import {readFile,writeFile,stat} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {validatePlan,backlogMarkdown,validateCourseDetails,courseBacklogMarkdown} from './team-plan.mjs';
const root=fileURLToPath(new URL('../',import.meta.url));
const readJSON=async file=>JSON.parse(await readFile(path.join(root,file),'utf8'));
const plan=await readJSON('docs/team/tasks.json'),roster=await readJSON('docs/team/roster.json');
validatePlan(plan,roster);
const members=await readJSON('docs/team/members.json');
assert.equal(members.UI?.length,3);assert.equal(members.backend?.length,5);
assert.equal(new Set([...members.UI,...members.backend]).size,8,'Duplicate team identity');
assert(members.backend.includes('ngocthuan1505'));
assert([...members.UI,...members.backend].every(u=>/^[a-z\d](?:[a-z\d-]{0,37}[a-z\d])?$/i.test(u)),'Invalid team username');
const course=validateCourseDetails(await readJSON('docs/course/deliverables.json'));
for(const file of new Set(plan.tasks.flatMap(t=>t.files))){const dest=path.resolve(root,file);assert(dest.startsWith(root));assert(await stat(dest),'Missing task source '+file);}
let map={};try{map=await readJSON('docs/team/github-issues.json');}catch(e){if(e.code!=='ENOENT')throw e;}
if(process.argv.includes('--write'))await writeFile(path.join(root,'docs/team/BACKLOG.md'),backlogMarkdown(plan,roster,map));
if(process.argv.includes('--write'))await writeFile(path.join(root,'docs/course/BACKLOG_CT.md'),courseBacklogMarkdown(course,await readJSON('docs/course/github-issues.json')));
for(const file of ['DOC_REPO_TRONG_5_PHUT.md','backend/README.md','docs/team/LOI_CONG_API.md','docs/team/CHON_VIEC.md','docs/team/HUONG_DAN_GUI_DISCORD.md','CONTRIBUTING.md','docs/product/USE_CASES.md','docs/testing/KIEM_THU_TICH_HOP.md','docs/team/KE_HOACH_TICH_HOP.md','docs/course/BACKLOG_CT.md','docs/team/BACKLOG.md','docs/product/DEMO_DA_CO.md','docs/team/CHAY_VA_TEST_DEMO.md','docs/testing/BASELINE_2026_11_05.md','AGENTS.md','docs/context/README.md','docs/context/LY_THUYET.md','docs/context/THUC_HANH.md','README.md','docs/team/README.md','docs/team/BOARD.md','docs/team/BAO_CAO.md','docs/team/ROLES.md','docs/team/RELEASE.md','docs/course/README.md','docs/course/HO_SO_DA_CO.md','docs/course/DE_BAI_GOC.md','docs/course/PROBLEM_BRIEF.md','docs/course/WBS.md','docs/course/CONTRACTS.md','docs/course/POC.md','docs/course/ALGORITHM.md','docs/course/EVALUATION.md','docs/reports/README.md','docs/reports/BAO_CAO_DO_AN.md','docs/architecture/CURRENT_STATE.md','docs/architecture/DATA_PLAN.md','docs/product/MVP.md','ops/greennode/README.md','ops/greennode/KHOI_PHUC.md','ops/greennode/legacy-bootstrap/README.md','server-kit/README.md']){
 const text=await readFile(path.join(root,file),'utf8');
 assert(!/nb-[a-f0-9]{8}-[a-f0-9-]{20,}-8888-|\b[a-z0-9]+(?:-[a-z0-9]+){2,}\.ngrok-free\.dev|sk-proj-[\w-]{20,}|AIza[\w-]{30,}/.test(text),'Private value in '+file);
 for(const match of text.matchAll(/\]\(([^)]+)\)/g)){
  const link=match[1];if(/^(?:https?:|mailto:|#)/.test(link))continue;
  const dest=path.resolve(path.dirname(path.join(root,file)),decodeURIComponent(link.split('#')[0]));
  assert(dest.startsWith(root),'Link leaves repo: '+file);await stat(dest);
 }
}
const example=await readJSON('ops/greennode/runtime-config.example.json');
assert.equal(example.HOST,'127.0.0.1');assert.equal(example.PORT,'4174');JSON.parse(example.APP_AI_CONFIG);
console.log('Team plan OK: 8 roles (3 UI + 5 backend), 24 tasks, 3 milestones, valid DAG/source paths/docs; no live server/key in team docs.');
