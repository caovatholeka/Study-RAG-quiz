# -*- coding: utf-8 -*-
"""
Service phân tích cấu trúc tài liệu (StructureExtractor).
Chuyển đổi danh sách TextBlock từ ParsedDocument thành cây phân cấp Chapter/Section/Subsection.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.document_parser import ParsedDocument, TextBlock

logger = logging.getLogger(__name__)


@dataclass
class ChapterNode:
    """Nút đại diện cho một chương hoặc mục trong cây phân cấp tài liệu."""
    number: int
    title: str
    content: str  # Toàn bộ nội dung văn bản của chương/mục
    level: str  # "chapter", "section", "subsection"
    children: List["ChapterNode"] = field(default_factory=list)
    topic_labels: List[str] = field(default_factory=list)
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class StructureExtractor:
    """
    Trích xuất cấu trúc phân cấp (cây chương/mục) từ ParsedDocument.
    Sử dụng kết hợp regex tiếng Việt, typography và các quy tắc phân cấp.
    """

    # Regex nhận diện Chương/Phần/Bài (Level 1)
    CHAPTER_PATTERNS = [
        re.compile(r"^(?:Chương|CHƯƠNG|Chapter|CHAPTER)\s+(\d+|[IVXLCDM]+)[.:\s]", re.IGNORECASE),
        re.compile(r"^(?:Bài|BÀI|Lesson)\s+(\d+)[.:\s]", re.IGNORECASE),
        re.compile(r"^(?:Phần|PHẦN|Part)\s+(\d+|[IVXLCDM]+)[.:\s]", re.IGNORECASE),
    ]

    # Regex nhận diện Mục/Tiết (Level 2 & 3)
    SECTION_PATTERNS = [
        re.compile(r"^(\d+\.)\s+"),
        re.compile(r"^(\d+\.\d+\.?)\s+"),
        re.compile(r"^([IVXLCDM]+\.)\s+"),
        re.compile(r"^([a-z][.\)])\s+", re.IGNORECASE),
    ]

    # Danh sách từ dừng (Stopwords) tiếng Việt và tiếng Anh để lọc khi trích xuất topic labels
    STOPWORDS = {
        "và", "của", "các", "những", "là", "trong", "với", "để", "về", "một", "cho",
        "được", "có", "này", "đó", "khi", "tại", "theo", "như", "nào", "gì", "sự",
        "việc", "phần", "chương", "bài", "mục", "tiết", "tổng", "quan", "cơ", "bản",
        "chi", "tiết", "nghiên", "cứu", "tìm", "hiểu", "hướng", "dẫn", "thực", "hành",
        "chapter", "section", "part", "lesson", "the", "a", "an", "and", "or", "of",
        "to", "in", "on", "at", "by", "for", "with", "about", "introduction", "overview",
    }

    def extract(self, parsed_doc: ParsedDocument) -> List[ChapterNode]:
        """
        Phân tích các block trong ParsedDocument và dựng thành cây phân cấp chương/mục.
        
        Args:
            parsed_doc: Kết quả trả về từ DocumentParser.
            
        Returns:
            Danh sách ChapterNode gốc (root chapters).
        """
        blocks = parsed_doc.blocks
        if not blocks:
            logger.warning("ParsedDocument không có khối văn bản nào.")
            return self._fallback_single_chapter(parsed_doc)

        # 1. Dựng cây phân cấp từ danh sách khối văn bản
        tree = self._build_tree(blocks, parsed_doc.metadata)

        # 2. Nếu không dựng được cây nào (không có heading) -> Fallback
        if not tree:
            logger.info("Không phát hiện được heading nào. Kích hoạt Fallback thành 1 chương duy nhất.")
            return self._fallback_single_chapter(parsed_doc)

        # 3. Gán nhãn chủ đề (topic labels) cho từng nút trong cây
        for node in tree:
            self._assign_topic_labels_recursive(node)

        logger.info(f"Trích xuất thành công {len(tree)} chương gốc.")
        return tree

    def _detect_heading_level(self, block: TextBlock) -> Optional[int]:
        """
        Xác định cấp độ heading (1: chapter, 2: section, 3: subsection) hoặc None.
        Kết hợp thông tin block.heading_level và regex matching trên nội dung.
        """
        text = block.text.strip()
        if not text:
            return None

        # 1. Kiểm tra CHAPTER_PATTERNS -> Level 1
        for pattern in self.CHAPTER_PATTERNS:
            if pattern.search(text):
                return 1

        # 2. Kiểm tra SECTION_PATTERNS
        # Kiểm tra tiểu mục (ví dụ "1.1.1", "a)", "a.") -> Level 3
        if re.search(r"^(\d+\.\d+\.\d+\.?)\s+", text) or re.search(r"^([a-z][.\)])\s+", text, re.IGNORECASE):
            return 3

        # Kiểm tra mục cấp 2 (ví dụ "1.1", "1.1.", "1.", "I.") -> Level 2
        for pattern in self.SECTION_PATTERNS:
            if pattern.search(text):
                return 2

        # 3. Dựa trên thông tin typography đã được parser gắn cờ
        if block.heading_level in (1, 2, 3):
            return block.heading_level

        if block.block_type == "heading":
            return block.heading_level or 2

        return None

    def _build_tree(self, blocks: List[TextBlock], metadata: Dict[str, Any]) -> List[ChapterNode]:
        """
        Dựng cây phân cấp từ danh sách phẳng các TextBlock.
        Merge các non-heading blocks vào heading gần nhất đứng trước.
        """
        roots: List[ChapterNode] = []
        current_chapter: Optional[ChapterNode] = None
        current_section: Optional[ChapterNode] = None
        current_node: Optional[ChapterNode] = None

        intro_blocks: List[TextBlock] = []
        chapter_counter = 1
        section_counter = 1
        subsection_counter = 1

        for block in blocks:
            level = self._detect_heading_level(block)

            if level is not None:
                title = block.text.strip()
                extracted_num = self._extract_number_from_title(title)

                if level == 1:
                    num = extracted_num if extracted_num is not None else chapter_counter
                    chapter_counter = max(chapter_counter + 1, num + 1)
                    section_counter = 1
                    subsection_counter = 1

                    node = ChapterNode(
                        number=num,
                        title=title,
                        content="",
                        level="chapter",
                        page_start=block.page_number,
                        page_end=block.page_number,
                    )

                    # Nếu có đoạn mở đầu trước chapter đầu tiên, tạo chương "Lời mở đầu"
                    if not roots and intro_blocks:
                        intro_node = self._create_intro_chapter(intro_blocks)
                        roots.append(intro_node)
                        intro_blocks = []

                    roots.append(node)
                    current_chapter = node
                    current_section = None
                    current_node = node

                elif level == 2:
                    num = extracted_num if extracted_num is not None else section_counter
                    section_counter = max(section_counter + 1, num + 1)
                    subsection_counter = 1

                    node = ChapterNode(
                        number=num,
                        title=title,
                        content="",
                        level="section",
                        page_start=block.page_number,
                        page_end=block.page_number,
                    )

                    # Nếu chưa có chapter cấp 1 nào, tạo chapter cấp 1 bao bọc hoặc đưa vào roots
                    if current_chapter is None:
                        # Tạo một chương cha mặc định
                        current_chapter = ChapterNode(
                            number=chapter_counter,
                            title=metadata.get("file_name", "Nội dung chính"),
                            content="",
                            level="chapter",
                            page_start=block.page_number,
                            page_end=block.page_number,
                        )
                        chapter_counter += 1
                        roots.append(current_chapter)

                    current_chapter.children.append(node)
                    current_section = node
                    current_node = node

                elif level == 3:
                    num = extracted_num if extracted_num is not None else subsection_counter
                    subsection_counter = max(subsection_counter + 1, num + 1)

                    node = ChapterNode(
                        number=num,
                        title=title,
                        content="",
                        level="subsection",
                        page_start=block.page_number,
                        page_end=block.page_number,
                    )

                    if current_section is not None:
                        current_section.children.append(node)
                    elif current_chapter is not None:
                        current_chapter.children.append(node)
                    else:
                        current_chapter = ChapterNode(
                            number=chapter_counter,
                            title=metadata.get("file_name", "Nội dung chính"),
                            content="",
                            level="chapter",
                            page_start=block.page_number,
                            page_end=block.page_number,
                        )
                        chapter_counter += 1
                        roots.append(current_chapter)
                        current_chapter.children.append(node)

                    current_node = node

            else:
                # Non-heading block: gộp vào heading gần nhất đứng trước
                text = block.text.strip()
                if not text:
                    continue

                if current_node is not None:
                    if current_node.content:
                        current_node.content += "\n\n" + text
                    else:
                        current_node.content = text

                    # Cập nhật trang kết thúc
                    if block.page_number is not None:
                        if current_node.page_start is None:
                            current_node.page_start = block.page_number
                        current_node.page_end = block.page_number
                else:
                    intro_blocks.append(block)

        # Nếu toàn bộ tài liệu chỉ có intro_blocks (không có heading) -> trả về rỗng để kích hoạt fallback
        if not roots and intro_blocks:
            return []

        return roots

    def _create_intro_chapter(self, blocks: List[TextBlock]) -> ChapterNode:
        """Tạo chương mở đầu cho các khối văn bản xuất hiện trước chương 1."""
        content = "\n\n".join(b.text.strip() for b in blocks if b.text.strip())
        page_start = blocks[0].page_number if blocks else None
        page_end = blocks[-1].page_number if blocks else None

        return ChapterNode(
            number=0,
            title="Lời mở đầu",
            content=content,
            level="chapter",
            page_start=page_start,
            page_end=page_end,
        )

    def _fallback_single_chapter(self, parsed_doc: ParsedDocument) -> List[ChapterNode]:
        """Coi toàn bộ tài liệu là 1 chương duy nhất khi không tìm thấy bất kỳ heading nào."""
        file_name = parsed_doc.metadata.get("file_name", "Tài liệu học tập")
        clean_title = re.sub(r"\.[a-zA-Z0-9]+$", "", file_name)

        full_content = "\n\n".join(b.text.strip() for b in parsed_doc.blocks if b.text.strip())
        page_start = parsed_doc.blocks[0].page_number if parsed_doc.blocks else 1
        page_end = parsed_doc.blocks[-1].page_number if parsed_doc.blocks else 1

        node = ChapterNode(
            number=1,
            title=clean_title,
            content=full_content,
            level="chapter",
            page_start=page_start,
            page_end=page_end,
        )
        self._assign_topic_labels(node)
        return [node]

    def _assign_topic_labels_recursive(self, node: ChapterNode) -> None:
        """Đệ quy gán nhãn chủ đề cho từng node và các node con."""
        self._assign_topic_labels(node)
        for child in node.children:
            self._assign_topic_labels_recursive(child)

    def _assign_topic_labels(self, chapter: ChapterNode) -> None:
        """
        Trích xuất từ khóa từ tiêu đề làm nhãn chủ đề (topic labels).
        Loại bỏ tiền tố heading và các từ dừng (stopwords).
        """
        title = chapter.title.strip()

        # Loại bỏ tiền tố Chương/Bài/Phần/Số La Mã/Số đếm
        clean_title = re.sub(
            r"^(?:(?:Chương|CHƯƠNG|Chapter|CHAPTER|Bài|BÀI|Lesson|Phần|PHẦN|Part)\s+(\d+|[IVXLCDM]+)|\d+(\.\d+)*|[IVXLCDM]+|[a-z][.\)])\s*[:.-]?\s*",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        if not clean_title:
            clean_title = title

        # Tách từ
        words = re.findall(r"[\w\u00C0-\u1EF9]+", clean_title.lower())
        filtered_words = [w for w in words if w not in self.STOPWORDS and len(w) >= 2 and not w.isdigit()]

        labels: List[str] = []

        # Thêm cụm tiêu đề đã làm sạch nếu độ dài hợp lý
        if 2 < len(clean_title) <= 50 and clean_title.lower() not in self.STOPWORDS:
            labels.append(clean_title)

        # Thêm các từ khóa đơn lẻ hoặc cụm 2 từ
        for i in range(len(filtered_words)):
            w = filtered_words[i]
            if w not in labels:
                labels.append(w)
            if i + 1 < len(filtered_words):
                bigram = f"{w} {filtered_words[i+1]}"
                if bigram not in labels:
                    labels.append(bigram)

        # Giới hạn tối đa 6 topic labels tiêu biểu
        chapter.topic_labels = labels[:6]

    def _extract_number_from_title(self, title: str) -> Optional[int]:
        """Trích xuất số thứ tự (Ả Rập hoặc La Mã) từ tiêu đề."""
        # 1. Khớp Chương/Bài/Phần
        for pattern in self.CHAPTER_PATTERNS:
            match = pattern.search(title)
            if match:
                val = match.group(1)
                if val.isdigit():
                    return int(val)
                elif re.match(r"^[IVXLCDM]+$", val, re.IGNORECASE):
                    return self._roman_to_int(val)

        # 2. Khớp số La Mã đứng đầu: "I. ", "II. "
        match_roman = re.match(r"^([IVXLCDM]+)\.\s+", title, re.IGNORECASE)
        if match_roman:
            return self._roman_to_int(match_roman.group(1))

        # 3. Khớp số Ả Rập đứng đầu: "1. ", "2. "
        match_arabic = re.match(r"^(\d+)(?:\.|\s+)", title)
        if match_arabic:
            return int(match_arabic.group(1))

        return None

    def _roman_to_int(self, roman: str) -> int:
        """Chuyển đổi số La Mã sang số nguyên int."""
        roman_values = {
            "I": 1, "V": 5, "X": 10, "L": 50,
            "C": 100, "D": 500, "M": 1000,
        }
        roman = roman.upper().strip()
        total = 0
        prev_val = 0

        for char in reversed(roman):
            val = roman_values.get(char, 0)
            if val >= prev_val:
                total += val
            else:
                total -= val
            prev_val = val

        return total if total > 0 else 1

