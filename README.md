# StudyRAG 📚

> **StudyRAG** (`Study-RAG-quiz`) là hệ thống hỗ trợ học tập và ôn tập thích ứng ứng dụng kiến trúc **Retrieval-Augmented Generation (RAG)** kết hợp các mô hình ngôn ngữ lớn (**OpenAI GPT-4o-mini** / **Google Gemini**), giúp tự động bóc tách cấu trúc tài liệu đa định dạng, truy xuất ngữ cảnh chính xác và sinh câu hỏi trắc nghiệm kèm quy trình xác thực 3 bước.

---

## 🚀 Tính năng nổi bật

- **Xử lý đa định dạng & Chống phân mảnh cấu trúc**:
  - Hỗ trợ tải lên và phân tích tài liệu **PDF, DOCX, TXT** (tự động phát hiện và cảnh báo đối với file PDF scan/ảnh không có lớp văn bản).
  - Bộ lọc chống phân mảnh thông minh (*Anti-fragmentation Firewall*): tự động loại trừ các phương án trắc nghiệm có sẵn (`A.`, `B.`, `C.`, `D.`), bullet points, câu thảo luận và gộp tiêu đề slide lặp lại liên tiếp (*Slide Deduplication*) để bảo toàn chuẩn xác cây Chương / Mục / Tiểu mục.
- **Vector Database & RAG Pipeline**:
  - Phân đoạn văn bản thông minh (Chunking) theo cấu trúc chương mục và đoạn văn tiếng Việt với độ gối đầu (overlap).
  - Sử dụng **ChromaDB** lưu trữ vector embeddings đa ngôn ngữ (`intfloat/multilingual-e5-large`, 1024 chiều).
  - Truy xuất ngữ cảnh liên quan (Cosine similarity) kèm trích dẫn nguồn chi tiết tới từng chương và số trang.
- **AI Quiz Generation & 3-Step Verification**:
  - Hỗ trợ linh hoạt **Dual LLM Provider**: **OpenAI** (`gpt-4o-mini`) và **Google Gemini** (`gemini-2.0-flash` / `gemini-1.5-flash`), tự động nhận diện theo tiền tố API key (`sk-` hoặc `AIza`/`AQ.`).
  - Kiểm soát chặt chẽ tổng số lượng câu hỏi theo yêu cầu (*Target Cap*), theo dõi tiến trình sinh nền theo thời gian thực (*Live Progress Polling*).
  - Pipeline xác thực 3 bước nghiêm ngặt: **RAG Retrieval** $\rightarrow$ **Fuzzy Matching** (RapidFuzz $\ge 70\%$) $\rightarrow$ **LLM Judge Verification & Auto-Correction**.
- **Làm bài, Chấm điểm tức thì & Lưu trữ bền vững**:
  - Hỗ trợ làm bài trắc nghiệm theo toàn bộ tài liệu, theo chương hoặc theo chủ đề.
  - Toàn bộ ngân hàng câu hỏi và lịch sử phiên thi được lưu trữ vĩnh viễn trong CSDL SQLite (`study_rag.db`).
  - Hệ thống ghi log tập trung (`backend/logs/studyrag.log`) và API xem log thời gian thực.

---

## 🛠 Kiến trúc công nghệ

- **Backend**:
  - Python 3.11+, FastAPI, Uvicorn
  - SQLAlchemy 2.0, SQLite
  - PyMuPDF (`fitz`), `python-docx`
  - ChromaDB, Sentence-Transformers (`intfloat/multilingual-e5-large`)
  - OpenAI SDK (`openai`) & Google GenAI SDK (`google-genai`)
  - RapidFuzz
- **Frontend**:
  - React 18, TypeScript, Vite
  - Tailwind CSS, Lucide React, Axios

---

## ⚙️ Cài đặt & Khởi chạy

### 1. Cấu hình môi trường & Cài đặt Backend
```bash
cd backend
python -m venv .venv
# Kích hoạt venv (Windows):
.venv\Scripts\activate

pip install -r requirements.txt

# Cấu hình biến môi trường
cp .env.example .env
# Mở file backend/.env và điền OPENAI_API_KEY (hoặc GEMINI_API_KEY)
```

Kiểm tra kết nối API Key nhanh (trên Windows):
```bash
test_key.bat
# Hoặc chạy trực tiếp bằng Python:
python test_gemini_key.py
```

Khởi chạy server FastAPI:
```bash
# Cách 1 (Windows): Chạy file script ở thư mục gốc
run_backend.bat

# Cách 2 (Thủ công trong thư mục backend):
python -m uvicorn app.main:app --reload --port 8000
```
- API Docs (Swagger UI): `http://localhost:8000/docs`
- Theo dõi logs thời gian thực (Windows): chạy `view_logs.bat`

### 2. Cài đặt & Khởi chạy Frontend
```bash
cd frontend
npm install

# Cách 1 (Windows): Chạy file script ở thư mục gốc
run_frontend.bat

# Cách 2 (Thủ công):
npm run dev
```
- Giao diện Web UI: `http://localhost:5173`

---

## 🧪 Kiểm thử (Testing)

Hệ thống có bộ unit test và integration test toàn diện (42 test cases):
```bash
cd backend

# Chạy toàn bộ test suite bằng unittest:
python -m unittest discover -s . -p "test_*.py"

# Hoặc chạy từng module test riêng biệt:
python test_quiz_system.py    # 21 tests: Sinh câu hỏi & Xác thực 3 bước
python test_quiz_api.py       # 5 tests: REST API Endpoints
python test_rag_pipeline.py   # 15 tests: Chunking, Embedding & RAG
python test_services.py       # Kiểm thử Parser, StructureExtractor & Pipeline
python test_integration.py    # Kiểm thử tích hợp End-to-End
```
