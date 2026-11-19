import {check, touch, uid} from './core.js';

export function openSketchBoard(context) {
 const selected=context.qget(context.getSelected());
 if(!selected){context.toast('Thêm hoặc chọn một câu để chèn hình.');return;}
 const examId=context.exam().id,questionId=selected.id,version=selected.v;
 context.modal('Vẽ phác cho câu hỏi',`
  <form id="sketch-board" class="sketch-board">
   <div class="sketch-tools">
    <label>Màu nét<select name="ink">
     <option value="#20302e">Đen</option>
     <option value="#176853">Xanh lục</option>
     <option value="#9e3b32">Đỏ</option>
    </select></label>
    <button type="button" data-sketch-undo disabled>Hoàn tác nét</button>
   </div>
   <canvas width="960" height="540" tabindex="0" aria-label="Bảng vẽ phác" aria-describedby="sketch-help"></canvas>
   <p id="sketch-help" class="hint">Dùng chuột hoặc chạm để vẽ. Với bàn phím, dùng phím mũi tên để di chuyển, nhấn Space để hạ hoặc nhấc bút.</p>
   <label>Chú thích hình<input name="caption" maxlength="120" placeholder="Ví dụ: Sơ đồ mạch điện"></label>
   <p data-sketch-status role="status"></p>
   <div class="modal-foot"><button type="submit" class="primary" disabled>Chèn hình vào câu</button></div>
  </form>`);
 const form=document.querySelector('#sketch-board'),canvas=form.querySelector('canvas');
 const surface=canvas.getContext('2d');
 if(!surface){form.querySelector('[data-sketch-status]').textContent='Trình duyệt chưa mở được bảng vẽ.';return;}
 const undo=form.querySelector('[data-sketch-undo]'),submit=form.querySelector('[type=submit]');
 const status=form.querySelector('[data-sketch-status]');
 const strokes=[];
 const cursor={x:canvas.width/2,y:canvas.height/2};
 let active=null,pointerId=null,showCursor=false,frame=null;

 function paint(displayCursor=showCursor){
  const target=surface;
  target.clearRect(0,0,canvas.width,canvas.height);
  target.lineWidth=4;
  target.lineJoin=target.lineCap='round';
  for(const {ink,points} of strokes){
   target.strokeStyle=target.fillStyle=ink;
   target.beginPath();
   const [first]=points;
   if(points.length===1){
    target.arc(first.x,first.y,2,0,Math.PI*2);
    target.fill();
   }else{
    target.moveTo(first.x,first.y);
    for(let i=1;i<points.length;i++)target.lineTo(points[i].x,points[i].y);
    target.stroke();
   }
  }
  if(displayCursor){
   target.strokeStyle='#176853';
   target.lineWidth=1.5;
   target.beginPath();
   target.moveTo(cursor.x-8,cursor.y);target.lineTo(cursor.x+8,cursor.y);
   target.moveTo(cursor.x,cursor.y-8);target.lineTo(cursor.x,cursor.y+8);
   target.stroke();
  }
  undo.disabled=submit.disabled=strokes.length===0;
 }
 function schedulePaint(){
  if(frame===null)frame=requestAnimationFrame(()=>{frame=null;if(canvas.isConnected)paint();});
 }
 function start(point){
  if(strokes.length===120){status.textContent='Đã đủ 120 nét. Hoàn tác một nét hoặc chèn hình hiện tại.';return;}
  active={ink:form.elements.ink.value,points:[point]};
  strokes.push(active);
  schedulePaint();
 }
 function append(point){
  if(!active)return;
  const last=active.points.at(-1);
  if(active.points.length>=1800||Math.hypot(point.x-last.x,point.y-last.y)<2)return;
  active.points.push(point);
  schedulePaint();
 }
 const pointAt=event=>{
  const rect=canvas.getBoundingClientRect();
  return {
   x:Math.max(0,Math.min(canvas.width,(event.clientX-rect.left)*canvas.width/rect.width)),
   y:Math.max(0,Math.min(canvas.height,(event.clientY-rect.top)*canvas.height/rect.height)),
  };
 };
 canvas.addEventListener('pointerdown',event=>{
  if(event.button!==0||pointerId!==null)return;
  event.preventDefault();
  canvas.focus();
  showCursor=false;
  pointerId=event.pointerId;
  canvas.setPointerCapture(pointerId);
  start(pointAt(event));
 });
 canvas.addEventListener('pointermove',event=>{
  if(event.pointerId===pointerId)append(pointAt(event));
 });
 canvas.addEventListener('pointerup',event=>{
  if(event.pointerId===pointerId)append(pointAt(event));
 });
 canvas.addEventListener('lostpointercapture',()=>{pointerId=null;active=null;});
 canvas.addEventListener('focus',()=>{showCursor=canvas.matches(':focus-visible');schedulePaint();});
 canvas.addEventListener('blur',()=>{showCursor=false;active=null;schedulePaint();});
 canvas.addEventListener('keydown',event=>{
  if(pointerId!==null)return;
  const moves={ArrowUp:[0,-8],ArrowDown:[0,8],ArrowLeft:[-8,0],ArrowRight:[8,0]};
  const delta=moves[event.key];
  if(!delta&&event.code!=='Space')return;
  event.preventDefault();
  showCursor=true;
  if(delta){
   cursor.x=Math.max(0,Math.min(canvas.width,cursor.x+delta[0]));
   cursor.y=Math.max(0,Math.min(canvas.height,cursor.y+delta[1]));
   append({...cursor});
  }else if(!event.repeat){
   if(active)active=null;
   else start({...cursor});
  }
  schedulePaint();
 });
 undo.addEventListener('click',()=>{
  active=null;
  strokes.pop();
  status.textContent='';
  schedulePaint();
 });
 form.addEventListener('submit',event=>{
  event.preventDefault();
  event.stopPropagation();
  if(!strokes.length)return;
  const current=context.exam(),question=context.qget(questionId);
  if(current.id!==examId||question?.v!==version||document.querySelector('.paper.ai-writing')){
   status.textContent='Câu đang chỉnh đã thay đổi. Mở lại bảng vẽ từ câu cần chèn.';
   return;
  }
  paint(false);
  const data=canvas.toDataURL('image/png'),caption=form.elements.caption.value.trim()||'Hình vẽ phác';
  context.change('Chèn hình vẽ phác vào câu',()=>{
   (question.images??=[]).push({id:uid(),data,caption});
   touch(question);
   check(current,question);
  });
  document.querySelector('#dialog').close();
  context.toast('Đã chèn hình vào câu.');
 });
}
