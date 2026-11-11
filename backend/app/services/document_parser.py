# -*- coding: utf-8 -*-
"""
Service phân tích tài liệu (PDF, DOCX, TXT) thành cấu trúc TextBlock và ParsedDocument.
Hỗ trợ nhận diện heading theo font-size, style, và regex tiếng Việt.
"""

import logging
import os
import re
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Đại diện cho một khối văn bản đã được phân tích từ tài liệu."""
    text: str
    page_number: Optional[int] = None
    font_size: Optional[float] = None
    is_bold: bool = False
    is_italic: bool = False
    heading_level: Optional[int] = None  # 1=chapter, 2=section, 3=subsection
    block_type: str = "paragraph"  # heading, paragraph, list_item, table


@dataclass
class ParsedDocument:
    """Cấu trúc dữ liệu chứa toàn bộ các khối văn bản và metadata của tài liệu."""
    blocks: List[TextBlock] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class DocumentParser:
    """
    Parser tài liệu đa định dạng (PDF, DOCX, TXT).
    Trích xuất cấu trúc văn bản kèm thông tin typography và thứ bậc heading.
    """

    # Regex patterns tiếng Việt nhận diện chương/phần/bài (Level 1)
    CHAPTER_PATTERNS = [
        re.compile(r"^(?:Chương|CHƯƠNG|Chapter|CHAPTER)\s+(\d+|[IVXLCDM]+)(?:[.:\s]|$)", re.IGNORECASE),
        re.compile(r"^(?:Bài|BÀI|Lesson)\s+(\d+)(?:[.:\s]|$)", re.IGNORECASE),
        re.compile(r"^(?:Phần|PHẦN|Part)\s+(\d+|[IVXLCDM]+)(?:[.:\s]|$)", re.IGNORECASE),
    ]

    # Regex patterns mục lớn (Level 2)
    SECTION_PATTERNS = [
        re.compile(r"^(\d+\.\d+\.?)\s+"),
        re.compile(r"^([IVXLCDM]+\.)\s+"),
        re.compile(r"^(?:Mục|Tiết|Chủ đề|Topic)\s+(\d+|[IVXLCDM]+)(?:[.:\s]|$)", re.IGNORECASE),
        re.compile(r"^(\d+\.)\s+"),
    ]

    # Regex patterns tiểu mục (Level 3)
    SUBSECTION_PATTERNS = [
        re.compile(r"^(\d+\.\d+\.\d+\.?)\s+"),
        re.compile(r"^([a-z]\))\s+"),
    ]

    # Regex nhận diện phương án trắc nghiệm (A. B. C. D. hoặc a. b. c. d.) - KHÔNG BAO GIỜ LÀ HEADING
    QUIZ_OPTION_PATTERN = re.compile(r"^[A-Da-d][.\)]\s+")

    # Regex nhận diện list item và bullet points
    LIST_PATTERNS = [
        re.compile(r"^[\u2022\u2023\u25E6\u2043\u2219\u25AA\u25AB\u25CF\u25CB\u2192\u2794\uF0E0\-\*\+]\s*"),
        re.compile(r"^\(\d+\)\s+"),
        re.compile(r"^\d+\)\s+"),
    ]

    # Danh sách các tiêu đề banner/hoạt động trong slide - không coi là chương/mục lớn để tránh phân mảnh tài liệu
    GENERIC_BANNERS = {
        "câu hỏi trắc nghiệm", "trắc nghiệm", "thảo luận", "bài tập", "ví dụ",
        "lưu ý", "tình huống khởi động", "cấu trúc nội dung", "tài liệu học tập",
        "mục tiêu", "tổng kết"
    }

    def parse(self, file_path: str, file_type: str) -> ParsedDocument:
        """
        Dispatch xử lý tài liệu theo định dạng file.
        
        Args:
            file_path: Đường dẫn tuyệt đối hoặc tương đối tới file.
            file_type: Loại file (pdf, docx, doc, txt).
            
        Returns:
            ParsedDocument chứa danh sách TextBlock và metadata.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file tại đường dẫn: {file_path}")

        file_type_norm = file_type.lower().lstrip(".")
        logger.info(f"Bắt đầu parse tài liệu: {file_path} (loại: {file_type_norm})")

        if file_type_norm == "pdf":
            return self._parse_pdf(file_path)
        elif file_type_norm in ("docx", "doc"):
            return self._parse_docx(file_path)
        elif file_type_norm == "txt":
            return self._parse_txt(file_path)
        else:
            raise ValueError(f"Định dạng file không được hỗ trợ: {file_type_norm}")

    # =========================================================================
    # PDF PARSER
    # =========================================================================

    def _parse_pdf(self, file_path: str) -> ParsedDocument:
        """Parse file PDF sử dụng PyMuPDF (fitz) với trích xuất font info và lọc header/footer."""
        try:
            import fitz
        except ImportError:
            try:
                import pymupdf as fitz
            except ImportError:
                raise ImportError("PyMuPDF chưa được cài đặt. Vui lòng cài bằng `pip install PyMuPDF`.")

        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info(f"PDF mở thành công: {total_pages} trang")

        # 1. Thu thập thống kê font size và phát hiện header/footer lặp lại
        all_font_sizes: List[float] = []
        top_candidates: Dict[str, Set[int]] = {}
        bottom_candidates: Dict[str, Set[int]] = {}

        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_height = page.rect.height
            page_dict = page.get_text("dict")

            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    bbox = block.get("bbox", (0, 0, 0, 0))
                    for line in block.get("lines", []):
                        raw_line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                        line_text = raw_line_text.replace("\xa0", " ").strip()
                        if not line_text:
                            continue

                        for span in line.get("spans", []):
                            txt = span.get("text", "").replace("\xa0", " ").strip()
                            if txt:
                                all_font_sizes.append(span.get("size", 12.0))

                        # Thu thập chuỗi ở vùng top (header) và bottom (footer)
                        line_bbox = line.get("bbox", bbox)
                        if line_bbox[1] < 55:  # Top 55pt
                            top_candidates.setdefault(line_text, set()).add(page_idx)
                        elif line_bbox[3] > page_height - 55:  # Bottom 55pt
                            bottom_candidates.setdefault(line_text, set()).add(page_idx)

        # Tính median font size
        median_font_size = statistics.median(all_font_sizes) if all_font_sizes else 12.0
        logger.debug(f"PDF median font size: {median_font_size:.2f}")

        # Xác định header/footer lặp lại (xuất hiện >= 2 trang nếu total_pages >= 2)
        # LƯU Ý: Không được coi các heading cấu trúc (Chương, 1.1, 1.2...) là artifact cần xóa,
        # vì trong bài giảng/slide, cùng một tiêu đề mục xuất hiện trên nhiều slide liên tiếp là bình thường!
        repeated_artifacts: Set[str] = set()
        if total_pages >= 2:
            for text, pages in {**top_candidates, **bottom_candidates}.items():
                if self._match_regex_heading(text) is not None:
                    continue
                if len(pages) >= 2:
                    repeated_artifacts.add(text)

        # 2. Parse nội dung chính
        parsed_blocks: List[TextBlock] = []

        for page_idx in range(total_pages):
            page_number = page_idx + 1
            page = doc[page_idx]
            page_height = page.rect.height
            page_dict = page.get_text("dict")

            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    bbox = block.get("bbox", (0, 0, 0, 0))
                    is_top_region = bbox[1] < 55
                    is_bottom_region = bbox[3] > page_height - 55

                    # Nhóm các line trong block theo heading hoặc paragraph
                    current_para_lines: List[str] = []
                    para_font_sizes: List[float] = []
                    para_bold_flags: List[bool] = []
                    para_italic_flags: List[bool] = []

                    for line in block.get("lines", []):
                        raw_line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                        line_text = raw_line_text.replace("\xa0", " ").strip()
                        if not line_text:
                            continue

                        line_bbox = line.get("bbox", bbox)
                        # Kiểm tra header/footer lặp lại hoặc dạng số trang đơn thuần
                        if (is_top_region or line_bbox[1] < 55) or (is_bottom_region or line_bbox[3] > page_height - 55):
                            if line_text in repeated_artifacts or re.match(r"^(?:Trang|Page)?\s*\d+(?:\s*/\s*\d+)?$", line_text, re.IGNORECASE):
                                continue

                        # Tính typography cho dòng này
                        line_sizes = [
                            span.get("size", median_font_size)
                            for span in line.get("spans", [])
                            if span.get("text", "").replace("\xa0", " ").strip()
                        ]
                        line_font_size = max(line_sizes) if line_sizes else median_font_size

                        line_is_bold = any(
                            (span.get("flags", 0) & 16 != 0)
                            or ("bold" in span.get("font", "").lower())
                            or ("black" in span.get("font", "").lower())
                            or ("heavy" in span.get("font", "").lower())
                            for span in line.get("spans", [])
                        )
                        line_is_italic = any(
                            (span.get("flags", 0) & 2 != 0)
                            or ("italic" in span.get("font", "").lower())
                            or ("oblique" in span.get("font", "").lower())
                            for span in line.get("spans", [])
                        )

                        # Kiểm tra xem dòng này có phải là heading không
                        heading_lvl = self._classify_heading(line_text, line_font_size, median_font_size, line_is_bold)

                        if heading_lvl is not None:
                            # Đẩy paragraph tích lũy trước đó ra nếu có
                            if current_para_lines:
                                self._flush_paragraph(
                                    parsed_blocks, current_para_lines, para_font_sizes,
                                    para_bold_flags, para_italic_flags, page_number
                                )
                                current_para_lines, para_font_sizes, para_bold_flags, para_italic_flags = [], [], [], []

                            # Thêm heading block
                            parsed_blocks.append(TextBlock(
                                text=line_text,
                                page_number=page_number,
                                font_size=line_font_size,
                                is_bold=line_is_bold,
                                is_italic=line_is_italic,
                                heading_level=heading_lvl,
                                block_type="heading",
                            ))
                        else:
                            # Tích lũy vào paragraph
                            current_para_lines.append(line_text)
                            para_font_sizes.append(line_font_size)
                            para_bold_flags.append(line_is_bold)
                            para_italic_flags.append(line_is_italic)

                    # Đẩy nốt phần paragraph còn lại của block
                    if current_para_lines:
                        self._flush_paragraph(
                            parsed_blocks, current_para_lines, para_font_sizes,
                            para_bold_flags, para_italic_flags, page_number
                        )

        doc.close()
        metadata = {
            "total_pages": total_pages,
            "file_type": "pdf",
            "file_name": os.path.basename(file_path),
            "median_font_size": median_font_size,
        }
        return ParsedDocument(blocks=parsed_blocks, metadata=metadata)

    # =========================================================================
    # DOCX PARSER
    # =========================================================================

    def _parse_docx(self, file_path: str) -> ParsedDocument:
        """Parse file DOCX/DOC sử dụng python-docx, duyệt styles và tables."""
        try:
            import docx
            from docx.text.paragraph import Paragraph
            from docx.table import Table
        except ImportError:
            raise ImportError("python-docx chưa được cài đặt. Vui lòng cài bằng `pip install python-docx`.")

        try:
            doc = docx.Document(file_path)
        except Exception as e:
            raise ValueError(f"Không thể mở file DOCX/DOC bằng python-docx: {e}")

        parsed_blocks: List[TextBlock] = []

        # Duyệt các phần tử theo thứ tự trong tài liệu (paragraphs và tables)
        for element in doc.element.body:
            tag = element.tag
            if tag.endswith("p"):
                p = Paragraph(element, doc)
                text = p.text.replace("\xa0", " ").strip()
                if not text:
                    continue

                style_name = p.style.name if p.style else ""
                heading_lvl: Optional[int] = None

                # 1. Nhận diện qua style name chuẩn của Word
                if "Heading 1" in style_name or "Title" in style_name:
                    heading_lvl = 1
                elif "Heading 2" in style_name or "Subtitle" in style_name:
                    heading_lvl = 2
                elif "Heading 3" in style_name:
                    heading_lvl = 3

                # 2. Kiểm tra typography qua runs
                has_runs = bool(p.runs)
                is_bold = has_runs and any(r.bold for r in p.runs) and all(r.bold for r in p.runs if r.text.strip())
                is_italic = has_runs and any(r.italic for r in p.runs) and all(r.italic for r in p.runs if r.text.strip())

                font_sizes = [r.font.size.pt for r in p.runs if r.font and r.font.size]
                font_size = max(font_sizes) if font_sizes else None

                # Nếu chưa có heading_lvl từ style, thử nhận diện bằng regex và bold runs
                if heading_lvl is None:
                    # Check regex
                    heading_lvl = self._match_regex_heading(text)
                    # Nếu không match regex, nhưng toàn bộ là bold và đoạn văn ngắn (< 150 ký tự)
                    if heading_lvl is None and is_bold and len(text) < 150 and not text.endswith("."):
                        if font_size and font_size >= 14:
                            heading_lvl = 1
                        else:
                            heading_lvl = 2

                # Xác định block_type
                if heading_lvl is not None:
                    block_type = "heading"
                elif style_name.startswith("List") or self._is_list_item(text):
                    block_type = "list_item"
                else:
                    block_type = "paragraph"

                parsed_blocks.append(TextBlock(
                    text=text,
                    page_number=None,
                    font_size=font_size,
                    is_bold=is_bold,
                    is_italic=is_italic,
                    heading_level=heading_lvl,
                    block_type=block_type,
                ))

            elif tag.endswith("tbl"):
                # Table element
                tbl = Table(element, doc)
                table_lines: List[str] = []
                for row in tbl.rows:
                    row_cells = [c.text.replace("\xa0", " ").strip().replace("\n", " ") for c in row.cells]
                    table_lines.append(" | ".join(row_cells))

                if table_lines:
                    table_text = "\n".join(table_lines)
                    parsed_blocks.append(TextBlock(
                        text=table_text,
                        page_number=None,
                        font_size=None,
                        is_bold=False,
                        is_italic=False,
                        heading_level=None,
                        block_type="table",
                    ))

        metadata = {
            "total_pages": None,
            "file_type": "docx",
            "file_name": os.path.basename(file_path),
        }
        return ParsedDocument(blocks=parsed_blocks, metadata=metadata)

    # =========================================================================
    # TXT PARSER
    # =========================================================================

    def _parse_txt(self, file_path: str) -> ParsedDocument:
        """Parse file TXT thuần với encoding UTF-8, phát hiện heading qua all-caps, patterns, và dòng trống."""
        encodings = ["utf-8", "utf-8-sig", "utf-16", "cp1258", "latin-1"]
        content: Optional[str] = None

        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, Exception):
                continue

        if content is None:
            raise ValueError(f"Không thể đọc file {file_path} với các bảng mã thông dụng.")

        lines = content.splitlines()
        parsed_blocks: List[TextBlock] = []
        i = 0
        n = len(lines)

        while i < n:
            raw_line = lines[i]
            line = raw_line.replace("\xa0", " ").strip()

            if not line:
                i += 1
                continue

            # Kiểm tra gạch chân kiểu Markdown (==== cho H1, ---- cho H2)
            if i + 1 < n:
                next_line = lines[i + 1].strip()
                if re.match(r"^={3,}$", next_line):
                    parsed_blocks.append(TextBlock(
                        text=line,
                        heading_level=1,
                        block_type="heading",
                    ))
                    i += 2
                    continue
                elif re.match(r"^-{3,}$", next_line) and not self._is_list_item(line):
                    parsed_blocks.append(TextBlock(
                        text=line,
                        heading_level=2,
                        block_type="heading",
                    ))
                    i += 2
                    continue

            # Kiểm tra regex patterns tiếng Việt
            heading_lvl = self._match_regex_heading(line)

            # Kiểm tra All-caps line (tiêu đề viết hoa toàn bộ)
            if heading_lvl is None and line.isupper() and 3 < len(line) < 120 and any(c.isalpha() for c in line):
                heading_lvl = 1

            if heading_lvl is not None:
                parsed_blocks.append(TextBlock(
                    text=line,
                    heading_level=heading_lvl,
                    block_type="heading",
                ))
            elif self._is_list_item(line):
                parsed_blocks.append(TextBlock(
                    text=line,
                    heading_level=None,
                    block_type="list_item",
                ))
            else:
                # Gom các dòng liền nhau thành một đoạn văn (paragraph) cho tới khi gặp dòng trống hoặc heading mới
                para_lines = [line]
                while i + 1 < n and lines[i + 1].strip():
                    next_text = lines[i + 1].replace("\xa0", " ").strip()
                    # Dừng gom nếu dòng tiếp theo là heading hoặc list item
                    if (self._match_regex_heading(next_text) is not None
                            or (next_text.isupper() and 3 < len(next_text) < 120)
                            or self._is_list_item(next_text)):
                        break
                    # Hoặc có underline ở dòng sau nữa
                    if i + 2 < n and re.match(r"^[=\-]{3,}$", lines[i + 2].strip()):
                        break

                    para_lines.append(next_text)
                    i += 1

                parsed_blocks.append(TextBlock(
                    text=" ".join(para_lines),
                    heading_level=None,
                    block_type="paragraph",
                ))

            i += 1

        metadata = {
            "total_pages": 1,
            "file_type": "txt",
            "file_name": os.path.basename(file_path),
        }
        return ParsedDocument(blocks=parsed_blocks, metadata=metadata)

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _is_banner(self, text: str) -> bool:
        """Kiểm tra có phải là banner slide hoạt động thông thường (câu hỏi trắc nghiệm, thảo luận...)."""
        clean = re.sub(r"^[0-9.:\s\-•]+", "", text.lower()).strip()
        return (
            clean in self.GENERIC_BANNERS
            or clean.startswith("câu hỏi trắc nghiệm")
            or clean.startswith("thảo luận")
        )

    def _classify_heading(
        self, text: str, font_size: float, median_font_size: float, is_bold: bool
    ) -> Optional[int]:
        """Phân loại mức độ heading (1, 2, 3) dựa trên regex và font characteristics."""
        trimmed = text.strip()
        if not trimmed or len(trimmed) < 2:
            return None

        # 0. Loại trừ tuyệt đối: bullet items, quiz options (A., B., C., D.), và slide banners
        if self._is_list_item(trimmed) or self.QUIZ_OPTION_PATTERN.match(trimmed) or self._is_banner(trimmed):
            return None

        # Loại trừ câu hỏi hoặc vế câu dở dang kết thúc bằng dấu ?, :, ;, , (trừ khi có từ khóa Chương/Bài)
        if trimmed.endswith("?") or trimmed.endswith(":") or trimmed.endswith(";") or trimmed.endswith(","):
            if not any(p.search(trimmed) for p in self.CHAPTER_PATTERNS):
                return None

        # 1. Ưu tiên regex patterns rõ ràng
        regex_lvl = self._match_regex_heading(trimmed)
        if regex_lvl is not None:
            # Nếu chỉ là dạng "1. ABC", kiểm tra thêm: phải viết hoa chữ đầu hoặc in đậm
            if re.match(r"^\d+\.\s+", trimmed) and not (is_bold or (len(trimmed) > 3 and trimmed[2:4].strip().isupper())):
                return None
            return regex_lvl

        # 2. Heading khi font_size > median_font_size * 1.25 AND is_bold AND len < 120
        if font_size > median_font_size * 1.25 and is_bold and len(trimmed) < 120:
            if font_size >= median_font_size * 1.6:
                return 1
            elif font_size >= median_font_size * 1.35:
                return 2
            else:
                return 3

        # 3. Tiêu đề in hoa toàn bộ (All-caps) và in đậm hoặc font lớn
        if trimmed.isupper() and 4 < len(trimmed) < 100 and any(c.isalpha() for c in trimmed):
            if is_bold or font_size >= median_font_size * 1.2:
                return 1 if font_size > median_font_size * 1.3 else 2

        return None

    def _match_regex_heading(self, text: str) -> Optional[int]:
        """Khớp regex patterns tiếng Việt/tiếng Anh để xác định heading level (1, 2, 3)."""
        trimmed = text.strip()
        if self._is_banner(trimmed):
            return None

        # Check Level 1: Chương, Bài, Phần
        for pattern in self.CHAPTER_PATTERNS:
            if pattern.search(trimmed):
                return 1

        # Check Level 3: Tiểu mục (1.1.1, a))
        for pattern in self.SUBSECTION_PATTERNS:
            if pattern.search(trimmed):
                return 3

        # Check Level 2: Mục (1.1, I., II., 1.)
        for pattern in self.SECTION_PATTERNS:
            if pattern.search(trimmed):
                # Nếu là single number 1. ABC: loại trừ câu hỏi/thảo luận
                if re.match(r"^\d+\.\s+", trimmed):
                    lower = trimmed.lower()
                    if any(w in lower for w in ["gì", "nào", "sao", "không", "ai", "đâu", "chỗ nào", "thế nào"]):
                        continue
                return 2

        return None

    def _is_list_item(self, text: str) -> bool:
        """Kiểm tra văn bản có phải là list item (bullet, gạch đầu dòng)."""
        trimmed = text.strip()
        return any(p.search(trimmed) for p in self.LIST_PATTERNS)

    def _flush_paragraph(
        self,
        blocks: List[TextBlock],
        lines: List[str],
        font_sizes: List[float],
        bold_flags: List[bool],
        italic_flags: List[bool],
        page_number: int,
    ) -> None:
        """Gộp các dòng paragraph và append TextBlock vào danh sách."""
        full_text = " ".join(lines).strip()
        if not full_text:
            return

        avg_size = statistics.mean(font_sizes) if font_sizes else None
        is_bold = all(bold_flags) if bold_flags else False
        is_italic = all(italic_flags) if italic_flags else False

        # Kiểm tra nếu là list item
        block_type = "list_item" if self._is_list_item(lines[0]) else "paragraph"

        blocks.append(TextBlock(
            text=full_text,
            page_number=page_number,
            font_size=avg_size,
            is_bold=is_bold,
            is_italic=is_italic,
            heading_level=None,
            block_type=block_type,
        ))
