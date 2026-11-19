// Chạy trên chế độ nhóm QA có hai tài khoản .test với kho trống.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright-core';

const base=process.env.POC_URL||'http://127.0.0.1:4185';
const output=path.resolve(process.argv[2]||'outputs/qa-kho-nhom');
const password='mat-khau-qa-18-11';
await fs.mkdir(output,{recursive:true});
const browser=await chromium.launch({
 executablePath:process.env.BROWSER_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',
 headless:true,
});
try {
 const context=await browser.newContext({viewport:{width:1366,height:900}});
 const guest=await context.request.get(base+'/api/kv?key=state');
 assert.equal(guest.status(),401);
 const first=await context.newPage(),second=await context.newPage();
 for(const page of [first,second])page.setDefaultTimeout(10000);
 async function login(page,email){
  await page.goto(base+'/login');
  await page.locator('#team-login [name=email]').fill(email);
  await page.locator('#team-login [name=password]').fill(password);
  await page.locator('#team-login button[type=submit]').click();
  await page.waitForURL(base+'/');
  await page.locator('.paper .title-input').waitFor();
 }
 const save=(page,status,name)=>page.waitForResponse(r=>{
  if(r.url()!==base+'/api/kv'||r.request().method()!=='PUT'||r.status()!==status)return false;
  const state=r.request().postDataJSON().value;
  return state.exams?.find(e=>e.id===state.current)?.title===name;
 });
 const title=page=>page.locator('.paper .title-input');
 async function create(page){
  await page.getByRole('button',{name:'Tạo đề mới',exact:true}).click();
  await page.locator('[data-action="create-blank"]:visible').click();
  await page.locator('[data-action="studio-question"]:visible').first().click();
  await page.locator('[data-action="studio-add-question"][data-type="essay"]').click();
 }
 async function rename(page,name,status=200){
  const [result]=await Promise.all([save(page,status,name),(async()=>{
   await title(page).fill(name);
   await title(page).blur();
  })()]);
  return result;
 }
 const library=page=>page.getByRole('button',{name:'Mở kho đề',exact:true}).click();
 const state=async()=>{const response=await context.request.get(base+'/api/kv?key=state');assert(response.ok());return response.json();};

 await login(first,'restore-admin@example.test');
 await create(first);
 await rename(first,'Kho A · đề Đại số');
 await library(first);
 await first.locator('#library-filter').fill('đại số');
 const result=first.locator('.wb-library-card:visible');
 assert.equal(await result.count(),1);
 await result.getByRole('button',{name:'Mở',exact:true}).click();
 assert.equal(await title(first).inputValue(),'Kho A · đề Đại số');
 const savedA=await state();
 const account=first.locator('[data-action="account"]:visible').first();
 await account.click();

 await login(second,'restore-member@example.test');
 await create(second);
 await rename(second,'Kho B · đề Hình học');
 const savedB=await state();
 await library(second);
 await second.locator('#library-filter').fill('đại số');
 assert.equal(await second.locator('.wb-library-card:visible').count(),0);
 const noResult=second.locator('#library-status[role="status"]');
 assert.equal(await noResult.textContent(),'Không tìm thấy đề phù hợp.');
 await second.locator('#library-filter').fill('  HÌNH HỌC  ');
 assert.equal(await second.locator('.wb-library-card:visible').count(),1);
 assert.equal(await noResult.textContent(),'');
 await second.keyboard.press('Escape');
 const logout=first.waitForResponse(r=>r.url()===base+'/api/account/logout');
 await first.locator('[data-action="logout"]:visible').click();
 assert.equal((await logout).status(),409);
 await first.keyboard.press('Escape');
 const conflict=await rename(first,'Nháp A từ tab cũ',409);
 assert.equal((await conflict.json()).code,'workspace_context_changed');
 assert.deepEqual(await state(),savedB);
 await second.reload();
 assert.equal(await title(second).inputValue(),'Kho B · đề Hình học');
 await login(second,'restore-admin@example.test');
 const after=await state();
 assert.deepEqual(after.value.exams.map(e=>e.id),savedA.value.exams.map(e=>e.id));
 assert(!after.value.exams.some(e=>e.title.includes('Kho B')));

 const phone=await browser.newPage({viewport:{width:390,height:844}});
 await login(phone,'restore-member@example.test');
 const entry=phone.getByRole('button',{name:'Mở kho đề',exact:true});
 for(let i=0;i<30 && !(await entry.evaluate(node=>node===document.activeElement));i++){
  await phone.keyboard.press('Tab');
 }
 assert(await entry.evaluate(node=>node.matches(':focus-visible')));
 await phone.keyboard.press('Enter');
 const search=phone.getByRole('textbox',{name:'Tìm trong kho đề'});
 await phone.keyboard.press('Tab');
 assert(await search.evaluate(node=>node.matches(':focus-visible')));
 await phone.keyboard.type('khong-co-de-nay');
 assert.equal(await phone.locator('#library-status').textContent(),'Không tìm thấy đề phù hợp.');
 const createEmpty=phone.getByRole('button',{name:'Tạo đề mới',exact:true}).last();
 for(let i=0;i<5 && !(await createEmpty.evaluate(node=>node===document.activeElement));i++){
  await phone.keyboard.press('Tab');
 }
 assert(await createEmpty.evaluate(node=>node.matches(':focus-visible')));
 await phone.keyboard.press('Escape');
 assert(await entry.evaluate(node=>node.matches(':focus-visible')));
 await phone.close();

 await fs.writeFile(path.join(output,'result.json'),JSON.stringify({
  scenario:'IT-01',guestDenied:true,createRenameFindOpen:true,twoAccountsIsolated:true,
  staleLogoutBlocked:true,staleWriteBlocked:true,reloadKeepsAccountB:true,
  noResultsStatus:true,mobileLibraryKeyboard:true,fixture:true,
 },null,2));
} finally {
 await browser.close();
}
