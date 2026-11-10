# StudyRAG 📚

> **StudyRAG** là hệ thống hỗ trợ học tập thông minh ứng dụng kiến trúc **Retrieval-Augmented Generation (RAG)** và mô hình ngôn ngữ lớn **Google Gemini**, giúp tự động bóc tách cấu trúc tài liệu, truy xuất ngữ cảnh thông minh và sinh câu hỏi trắc nghiệm tự động kèm xác thực 3 bước.

---

## 🚀 Tính năng nổi bật

- **Xử lý đa định dạng tài liệu**: Hỗ trợ tải lên và phân tích tài liệu PDF, DOCX, TXT.
- **Trích xuất phân cấp thông minh**: Tự động nhận diện cấu trúc Chương / Mục / Tiểu mục và gán các nhãn chủ đề (`topic_labels`).
- **Vector Database & RAG Pipeline**:
  - Phân đoạn văn bản thông minh (Chunking) theo cấu trúc chương mục và đoạn văn tiếng Việt với độ gối đầu (overlap).
  - Sử dụng ChromaDB lưu trữ vector embeddings đa ngôn ngữ (`intfloat/multilingual-e5-large`).
  - Truy xuất ngữ cảnh liên quan (Cosine similarity) kèm trích dẫn nguồn chi tiết.
- **AI Quiz Generation & 3-Step Verification**:
  - Sinh hàng loạt câu hỏi trắc nghiệm chất lượng cao từ nội dung chương với Google Gemini (`google-genai` SDK).
  - Pipeline xác thực 3 bước nghiêm ngặt: **RAG Retrieval** $\rightarrow$ **Fuzzy Matching** (ngưỡng 70%) $\rightarrow$ **LLM Verification & Auto-Correction**.
  - Đảm bảo câu hỏi có 4 phương án, distractors hợp lý, kiểm tra hiểu sâu và đáp án được chứng minh từ tài liệu.
- **Làm bài & Chấm điểm tức thì**:
  - Hỗ trợ làm bài trắc nghiệm theo toàn bộ tài liệu, theo chương hoặc theo chủ đề.
  - Chấm điểm thang 10, hiển thị kết quả chi tiết kèm lời giải thích và trích dẫn tài liệu gốc.

---

## 🛠 Kiến trúc công nghệ

- **Backend**:
  - Python 3.11+, FastAPI, Uvicorn
  - SQLAlchemy 2.0, SQLite
  - PyMuPDF, python-docx, unstructured
  - ChromaDB, Sentence-Transformers
  - Google Gemini API (`google-genai` SDK)
  - RapidFuzz
- **Frontend**:
  - React 18, TypeScript, Vite
  - Tailwind CSS, Lucide React, Axios

---

## ⚙️ Cài đặt & Khởi chạy

### 1. Backend
```bash
cd backend
python -m venv .venv
# Kích hoạt venv (Windows):
.venv\Scripts\activate

pip install -r requirements.txt

# Cấu hình biến môi trường
cp .env.example .env
# Mở file .env và điền GEMINI_API_KEY

# Khởi chạy server FastAPI:
python -m uvicorn app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/docs`

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
- UI: `http://localhost:5173`

---

## 🧪 Kiểm thử (Testing)

Hệ thống có bộ unit và integration test toàn diện:
```bash
cd backend
# Chạy bộ test Quiz System (21 tests):
python test_quiz_system.py

# Chạy test REST API Endpoints (5 tests):
python test_quiz_api.py

# Chạy test tích hợp RAG Pipeline:
python test_integration.py
```
