# Thành phần bên thứ ba

- KaTeX 0.16.22: MIT, https://github.com/KaTeX/KaTeX/blob/v0.16.22/LICENSE
- Tesseract.js 7.0.0: Apache-2.0, https://github.com/naptha/tesseract.js
- tessdata_fast (vie/eng): Apache-2.0, https://github.com/tesseract-ocr/tessdata_fast
- docx 9.6.1: MIT, https://github.com/dolanmiu/docx
- PDF.js 5.6.205: Apache-2.0, https://github.com/mozilla/pdf.js
- JSZip 3.10.1: MIT hoặc GPLv3, sử dụng theo MIT, https://github.com/Stuk/jszip
- @napi-rs/canvas 0.1.100: MIT, https://github.com/Brooooooklyn/canvas
- Playwright 1.62.1: Apache-2.0, https://github.com/microsoft/playwright
- PPTXGenJS 4.0.1 (kiểm thử): MIT, https://github.com/gitbrent/PptxGenJS
- Runtime portable Ollama và llama.cpp: giấy phép tương ứng trong bản phân phối chính thức; runtime không nằm trong ZIP bàn giao.
- Qwen3:4b: Apache-2.0 theo trang mô hình chính thức; trọng số không nằm trong ZIP bàn giao.

Các gói npm giữ tệp LICENSE trong thư mục cài đặt. assets/katex/LICENSE kèm nguyên văn giấy phép KaTeX. Mã app sử dụng dữ liệu mẫu nhóm tự soạn, không kèm sách giáo khoa thương mại.

- TipTap 3.32.0/extensions và ProseMirror: MIT, https://github.com/ueberdosis/tiptap ; https://github.com/ProseMirror . Giấy phép bundle: assets/editor-engine.js.LEGAL.txt.
- mhchem đi kèm KaTeX 0.16.22: MIT; giữ giấy phép KaTeX trong assets/katex/LICENSE.
- esbuild 0.25.12 (build): MIT, https://github.com/evanw/esbuild .
- xml-js 1.6.11 (đọc OOXML/OMML): MIT, https://github.com/nashwaan/xml-js . Gói npm giữ LICENSE gốc.
- MathLive 0.111.1: MIT, https://github.com/arnog/mathlive . Vendored từ gói npm chính thức; LICENSE.txt trong assets/mathlive/. Phông cục bộ của gói được giữ cùng thư viện. Chỉ tải module khi mở bộ nhập công thức.

- python-docx 1.2.0: MIT, https://github.com/python-openxml/python-docx ; backend tạo DOCX rich/OMML bằng Python.
- lxml 6.1.3: BSD-3-Clause, https://github.com/lxml/lxml ; dependency của python-docx.
- Pillow 13.0.0: HPND, https://github.com/python-pillow/Pillow ; đọc/kiểm ảnh PNG/JPEG/WebP, bản phân phối giữ giấy phép codec liên quan.
- Công thức Word dùng KaTeX/mhchem đã có qua Chrome/Edge headless local để tạo MathML; Python chuyển OMML và đóng gói. Không gọi Node API, không cần Word cài sẵn để xuất. Word chỉ dùng riêng trong QA tại máy này.
