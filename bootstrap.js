// Lỗi nạp module xảy ra trước init(); cần đưa người dùng ra khỏi màn hình chờ.
import('./app.js').catch(error=>{
 console.error('Không tải được giao diện bàn soạn:',error);
 const root=document.querySelector('#app');
 const panel=document.createElement('section');panel.style.padding='40px';panel.setAttribute('role','alert');
 const heading=document.createElement('h1');heading.textContent='Chưa tải được bàn soạn';
 const message=document.createElement('p');message.textContent='Một phần giao diện chưa tải được hoặc đang dùng phiên bản cũ trong bộ nhớ đệm. Đề và kết nối đã lưu vẫn được giữ.';
 const reload=document.createElement('button');reload.type='button';reload.textContent='Tải lại giao diện';reload.onclick=()=>location.reload();
 const help=document.createElement('p');help.textContent='Nếu vẫn gặp lỗi, nhấn Ctrl + Shift + R để tải mới các tệp giao diện.';
 panel.append(heading,message,reload,help);root.replaceChildren(panel);
});
