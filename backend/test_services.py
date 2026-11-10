# -*- coding: utf-8 -*-
"""
Script kiểm thử toàn diện cho các service:
- DocumentParser (PDF, DOCX, TXT)
- StructureExtractor (Phân cấp, Topic labels, Fallback, Roman numbers)
- DocumentProcessor (End-to-end pipeline, DB integration, Error handling)
"""

import os
import sys
import tempfile
import shutil

# Thêm thư mục backend vào sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import fitz  # PyMuPDF
import docx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.document import Document, Chapter, DocumentStatus, ChapterLevel
from app.services.document_parser import DocumentParser, TextBlock, ParsedDocument
from app.services.structure_extractor import StructureExtractor, ChapterNode
from app.services.document_processor import DocumentProcessor


def create_sample_txt(filepath: str):
    """Tạo file TXT mẫu có cấu trúc chương/mục."""
    content = """LỜI NÓI ĐẦU
Đây là tài liệu hướng dẫn học tập hệ thống phân tán và RAG.
Tài liệu cung cấp kiến thức nền tảng và nâng cao.

Chương 1: Tổng quan về Kiến trúc RAG
Hệ thống RAG kết hợp giữa mô hình truy xuất và mô hình sinh ngôn ngữ.

1. Khái niệm cơ bản
RAG là viết tắt của Retrieval-Augmented Generation.
Các thành phần chính gồm:
- Document Parser
- Vector Database
- Generator LLM

1.1. Vector Database
Vector database lưu trữ các vector embeddings để tìm kiếm theo độ tương đồng cosine.

a) ChromaDB
ChromaDB là cơ sở dữ liệu vector mã nguồn mở gọn nhẹ.

Chương 2: Đánh giá và Kiểm thử
Đánh giá chất lượng của mô hình RAG qua các chỉ số retrieval và generation.
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def create_sample_docx(filepath: str):
    """Tạo file DOCX mẫu có Heading 1, 2, 3 và table."""
    doc = docx.Document()
    doc.add_heading("Chương 1: Giới thiệu Python", level=1)
    doc.add_paragraph("Python là một ngôn ngữ lập trình bậc cao, dễ học và mạnh mẽ.")
    
    doc.add_heading("1.1. Cú pháp cơ bản", level=2)
    doc.add_paragraph("Cú pháp Python sử dụng thụt lề để xác định khối lệnh.")

    doc.add_heading("1.1.1. Biến và Kiểu dữ liệu", level=3)
    p = doc.add_paragraph()
    r = p.add_run("Các kiểu dữ liệu cơ bản: int, float, str, bool.")
    
    # Bảng mẫu
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Kiểu dữ liệu"
    table.cell(0, 1).text = "Ví dụ"
    table.cell(1, 0).text = "int"
    table.cell(1, 1).text = "42"
    
    doc.add_heading("Chương 2: Hướng đối tượng trong Python", level=1)
    doc.add_paragraph("Lập trình hướng đối tượng (OOP) hỗ trợ đóng gói, kế thừa và đa hình.")
    
    doc.save(filepath)


def create_sample_pdf(filepath: str):
    """Tạo file PDF mẫu có font heading, lặp header/footer nhiều trang."""
    doc = fitz.open()
    font_regular = "C:/Windows/Fonts/arial.ttf"
    font_bold = "C:/Windows/Fonts/arialbd.ttf"
    
    # Trang 1
    page1 = doc.new_page(width=595, height=842)
    if os.path.exists(font_regular):
        page1.insert_font(fontname="ArialVN", fontfile=font_regular)
    if os.path.exists(font_bold):
        page1.insert_font(fontname="ArialBoldVN", fontfile=font_bold)
        
    fn_reg = "ArialVN" if os.path.exists(font_regular) else "helv"
    fn_bold = "ArialBoldVN" if os.path.exists(font_bold) else "times-bold"

    # Header lặp lại
    page1.insert_text((50, 40), "GIÁO TRÌNH HỆ THỐNG THÔNG TIN", fontsize=9, fontname=fn_reg)
    # Heading Chương 1 (font size lớn 20, bold)
    page1.insert_text((50, 120), "Chương I: Tổng quan Hệ thống", fontsize=20, fontname=fn_bold)
    page1.insert_text((50, 160), "Hệ thống thông tin quản lý dữ liệu cho doanh nghiệp.", fontsize=12, fontname=fn_reg)
    # Heading Section (font size 15, bold)
    page1.insert_text((50, 200), "1. Phân loại hệ thống", fontsize=15, fontname=fn_bold)
    page1.insert_text((50, 230), "Có nhiều loại hệ thống thông tin phục vụ nhiều cấp quản lý.", fontsize=12, fontname=fn_reg)
    # Footer lặp lại
    page1.insert_text((250, 810), "Trang 1 / 2", fontsize=9, fontname=fn_reg)
    
    # Trang 2
    page2 = doc.new_page(width=595, height=842)
    if os.path.exists(font_regular):
        page2.insert_font(fontname="ArialVN", fontfile=font_regular)
    if os.path.exists(font_bold):
        page2.insert_font(fontname="ArialBoldVN", fontfile=font_bold)

    # Header lặp lại
    page2.insert_text((50, 40), "GIÁO TRÌNH HỆ THỐNG THÔNG TIN", fontsize=9, fontname=fn_reg)
    # Heading Chương 2
    page2.insert_text((50, 120), "Chương II: Cơ sở Dữ liệu Quan hệ", fontsize=20, fontname=fn_bold)
    page2.insert_text((50, 160), "Cơ sở dữ liệu quan hệ tổ chức dữ liệu theo các bảng hai chiều.", fontsize=12, fontname=fn_reg)
    # Footer lặp lại
    page2.insert_text((250, 810), "Trang 2 / 2", fontsize=9, fontname=fn_reg)
    
    doc.save(filepath)
    doc.close()


def test_document_parser():
    """Kiểm tra DocumentParser với TXT, DOCX, PDF."""
    print("--- [TEST 1] DocumentParser ---")
    parser = DocumentParser()
    test_dir = tempfile.mkdtemp()
    
    try:
        # 1. Test TXT
        txt_path = os.path.join(test_dir, "sample.txt")
        create_sample_txt(txt_path)
        parsed_txt = parser.parse(txt_path, "txt")
        assert len(parsed_txt.blocks) > 0, "Parsed TXT blocks should not be empty"
        headings_txt = [b for b in parsed_txt.blocks if b.block_type == "heading"]
        assert len(headings_txt) >= 2, f"Should detect at least 2 headings in TXT, got {len(headings_txt)}"
        print(f"✅ TXT Parsed successfully: {len(parsed_txt.blocks)} blocks, {len(headings_txt)} headings")
        
        # 2. Test DOCX
        docx_path = os.path.join(test_dir, "sample.docx")
        create_sample_docx(docx_path)
        parsed_docx = parser.parse(docx_path, "docx")
        assert len(parsed_docx.blocks) > 0, "Parsed DOCX blocks should not be empty"
        headings_docx = [b for b in parsed_docx.blocks if b.block_type == "heading"]
        tables_docx = [b for b in parsed_docx.blocks if b.block_type == "table"]
        assert len(headings_docx) >= 3, f"Should detect at least 3 headings in DOCX, got {len(headings_docx)}"
        assert len(tables_docx) >= 1, "Should detect at least 1 table in DOCX"
        print(f"✅ DOCX Parsed successfully: {len(parsed_docx.blocks)} blocks, {len(headings_docx)} headings, {len(tables_docx)} tables")

        # 3. Test PDF
        pdf_path = os.path.join(test_dir, "sample.pdf")
        create_sample_pdf(pdf_path)
        parsed_pdf = parser.parse(pdf_path, "pdf")
        assert len(parsed_pdf.blocks) > 0, "Parsed PDF blocks should not be empty"
        assert parsed_pdf.metadata["total_pages"] == 2, "PDF should have 2 pages"
        headings_pdf = [b for b in parsed_pdf.blocks if b.block_type == "heading"]
        assert len(headings_pdf) >= 2, f"Should detect at least 2 headings in PDF, got {len(headings_pdf)}"
        # Check repeated header stripped
        header_texts = [b.text for b in parsed_pdf.blocks if "GIÁO TRÌNH HỆ THỐNG THÔNG TIN" in b.text]
        assert len(header_texts) == 0, "Repeated header should be stripped"
        print(f"✅ PDF Parsed successfully: {len(parsed_pdf.blocks)} blocks, {len(headings_pdf)} headings, repeated headers stripped")

    finally:
        shutil.rmtree(test_dir)


def test_structure_extractor():
    """Kiểm tra StructureExtractor: phân cấp cây, La Mã, topic labels, fallback."""
    print("\n--- [TEST 2] StructureExtractor ---")
    extractor = StructureExtractor()

    # 1. Test Roman to int
    assert extractor._roman_to_int("I") == 1
    assert extractor._roman_to_int("IV") == 4
    assert extractor._roman_to_int("IX") == 9
    assert extractor._roman_to_int("XIV") == 14
    assert extractor._roman_to_int("XX") == 20
    print("✅ _roman_to_int conversion verified")

    # 2. Test Tree building with hierarchy
    blocks = [
        TextBlock(text="Giới thiệu mở đầu về tài liệu", block_type="paragraph", page_number=1),
        TextBlock(text="Chương 1: Kiến trúc RAG cơ bản", block_type="heading", heading_level=1, page_number=1),
        TextBlock(text="Nội dung tổng quát chương 1", block_type="paragraph", page_number=1),
        TextBlock(text="1.1. Embedding Model", block_type="heading", heading_level=2, page_number=2),
        TextBlock(text="Chi tiết về Embedding Model", block_type="paragraph", page_number=2),
        TextBlock(text="1.1.1. Multilingual E5", block_type="heading", heading_level=3, page_number=2),
        TextBlock(text="Chi tiết về Multilingual E5", block_type="paragraph", page_number=2),
        TextBlock(text="Chương 2: Vector Database", block_type="heading", heading_level=1, page_number=3),
        TextBlock(text="Nội dung chương 2", block_type="paragraph", page_number=3),
    ]
    parsed_doc = ParsedDocument(blocks=blocks, metadata={"file_name": "test_rag.pdf"})
    tree = extractor.extract(parsed_doc)

    # Kiểm tra cây
    assert len(tree) >= 2, f"Tree should have at least 2 root chapters, got {len(tree)}"
    ch1 = [node for node in tree if "Chương 1" in node.title or "Kiến trúc RAG" in node.title][0]
    assert ch1.number == 1
    assert len(ch1.children) == 1, "Chương 1 should have 1 section"
    sec1 = ch1.children[0]
    assert "1.1" in sec1.title
    assert len(sec1.children) == 1, "Section 1.1 should have 1 subsection"
    assert "1.1.1" in sec1.children[0].title
    assert len(ch1.topic_labels) > 0, "Chương 1 should have topic labels"
    print(f"✅ Tree hierarchy built properly: {len(tree)} roots, nested children verified")
    print(f"   Topic labels for Chapter 1: {ch1.topic_labels}")

    # 3. Test Fallback
    no_heading_blocks = [
        TextBlock(text="Đoạn văn 1 không có tiêu đề", block_type="paragraph", page_number=1),
        TextBlock(text="Đoạn văn 2 tiếp tục nội dung", block_type="paragraph", page_number=1),
    ]
    doc_fallback = ParsedDocument(blocks=no_heading_blocks, metadata={"file_name": "tailieu_onthi.txt"})
    tree_fallback = extractor.extract(doc_fallback)
    assert len(tree_fallback) == 1, "Fallback should return exactly 1 chapter"
    assert tree_fallback[0].title == "tailieu_onthi"
    assert "Đoạn văn 1" in tree_fallback[0].content
    assert "Đoạn văn 2" in tree_fallback[0].content
    print("✅ Fallback single-chapter verified successfully")


def test_document_processor():
    """Kiểm tra DocumentProcessor: database integration, pipeline, và error handling."""
    print("\n--- [TEST 3] DocumentProcessor Pipeline ---")
    # Khởi tạo in-memory SQLite DB cho test
    test_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(bind=test_engine)
    db = TestSessionLocal()

    test_dir = tempfile.mkdtemp()
    try:
        # Tạo file mẫu
        sample_path = os.path.join(test_dir, "test_doc.txt")
        create_sample_txt(sample_path)

        # 1. Tạo Document record
        doc = Document(
            filename="test_doc.txt",
            original_filename="Tài liệu mẫu RAG.txt",
            file_path=sample_path,
            status=DocumentStatus.PROCESSING,
            file_type="txt",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        doc_id = doc.id
        print(f"Created test Document in DB with ID: {doc_id}")

        # 2. Chạy DocumentProcessor
        processor = DocumentProcessor()
        processed_doc = processor.process_document(doc_id, db)

        # Kiểm tra kết quả
        assert processed_doc.status == DocumentStatus.READY, f"Document status should be READY, got {processed_doc.status}"
        assert processed_doc.total_chapters > 0, "total_chapters should be > 0"
        
        # Kiểm tra Chapters trong DB
        chapters_in_db = db.query(Chapter).filter(Chapter.document_id == doc_id).all()
        assert len(chapters_in_db) == processed_doc.total_chapters, "DB chapters count should match total_chapters"
        
        # Kiểm tra quan hệ parent_id
        child_chapters = [c for c in chapters_in_db if c.parent_id is not None]
        assert len(child_chapters) > 0, "Should have child chapters with parent_id set"
        
        print(f"✅ Pipeline executed successfully: Document {doc_id} is READY, total {len(chapters_in_db)} chapters saved.")
        for ch in chapters_in_db:
            parent_info = f"(parent_id={ch.parent_id})" if ch.parent_id else "(root)"
            print(f"   - [{ch.level.value}] #{ch.chapter_number} {ch.title} {parent_info}")

        # 3. Test Error Handling (file không tồn tại)
        error_doc = Document(
            filename="not_found.pdf",
            original_filename="not_found.pdf",
            file_path=os.path.join(test_dir, "non_existent_file.pdf"),
            status=DocumentStatus.PROCESSING,
            file_type="pdf",
        )
        db.add(error_doc)
        db.commit()
        db.refresh(error_doc)

        error_caught = False
        try:
            processor.process_document(error_doc.id, db)
        except Exception:
            error_caught = True

        assert error_caught, "Processor should raise an exception for missing file"
        db.refresh(error_doc)
        assert error_doc.status == DocumentStatus.ERROR, f"Status should be ERROR, got {error_doc.status}"
        print(f"✅ Error handling verified: missing file set status to ERROR")

    finally:
        db.close()
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    print("================ BẮT ĐẦU KIỂM THỬ STUDYRAG SERVICES ================")
    test_document_parser()
    test_structure_extractor()
    test_document_processor()
    print("\n================ TẤT CẢ CÁC BÀI TEST ĐÃ VƯỢT QUA XUẤT SẮC! ================")
