# -*- coding: utf-8 -*-
"""
Các template prompt cho hệ thống AI Quiz Generation và Verification trong StudyRAG.
Định nghĩa các hằng số prompt cho:
- Sinh câu hỏi trắc nghiệm (QUIZ_GENERATION_PROMPT)
- Xác thực câu hỏi và đáp án với tài liệu gốc (QUIZ_VERIFICATION_PROMPT)
- Sinh giải thích chi tiết cho câu sai (EXPLANATION_GENERATION_PROMPT)
- Trích xuất nhãn chủ đề từ nội dung chương (TOPIC_EXTRACTION_PROMPT)
"""

QUIZ_GENERATION_PROMPT = """Bạn là chuyên gia giáo dục và biên soạn đề thi trắc nghiệm chuyên nghiệp.
Nhiệm vụ của bạn là tạo chính xác {num_questions} câu hỏi trắc nghiệm chất lượng cao dựa trên nội dung chương học dưới đây.

=== THÔNG TIN CHƯƠNG HỌC ===
Tiêu đề: {chapter_title}
Nội dung:
{content}

=== PHÂN BỔ ĐỘ KHÓ YÊU CẦU ===
{difficulty_distribution}

=== YÊU CẦU NGHIÊM NGẶT ===
1. Toàn bộ câu hỏi, phương án và giải thích bắt buộc viết bằng TIẾNG VIỆT chuẩn xác, rõ ràng.
2. Câu hỏi phải kiểm tra mức độ HIỂU SÂU, phân tích, suy luận và áp dụng khái niệm, KHÔNG chỉ đơn thuần học vẹt hay ghi nhớ từng từ bề mặt.
3. Mỗi câu hỏi bắt buộc có đúng 4 phương án lựa chọn: "A", "B", "C", "D".
4. Các phương án sai (distractors) phải HỢP LÝ, có tính thuyết phục, phản ánh các hiểu lầm thường gặp của người học, tuyệt đối không được quá vô lý hoặc ngô nghê.
5. Đáp án đúng phải CHÍNH XÁC TUYỆT ĐỐI và CÓ THỂ XÁC MINH RÕ RÀNG từ nội dung đã cung cấp ở trên.
6. Độ khó (difficulty) của mỗi câu phải là một trong 3 giá trị: "easy", "medium", "hard".
7. Phần giải thích (explanation) phải ngắn gọn, súc tích (1-3 câu), chỉ rõ lý do vì sao đáp án đó đúng dựa vào nội dung.
8. Thẻ chủ đề (topic_tag) ngắn gọn (1-4 từ) phản ánh khái niệm hoặc chủ đề trọng tâm của câu hỏi.

=== ĐỊNH DẠNG ĐẦU RA (BẮT BUỘC) ===
Chỉ trả về DUY NHẤT một JSON array hợp lệ, không có thêm bất kỳ lời dẫn giải hay markdown code block bao ngoài.
Cấu trúc mỗi phần tử:
[
  {{
    "question": "Nội dung câu hỏi trắc nghiệm...",
    "options": {{
      "A": "Nội dung phương án A",
      "B": "Nội dung phương án B",
      "C": "Nội dung phương án C",
      "D": "Nội dung phương án D"
    }},
    "correct_answer": "A",
    "difficulty": "medium",
    "explanation": "Giải thích ngắn gọn tại sao phương án được chọn là đúng...",
    "topic_tag": "Tên chủ đề"
  }}
]
"""

QUIZ_VERIFICATION_PROMPT = """Bạn là chuyên gia kiểm định chất lượng đề thi và tính xác thực thông tin.
Nhiệm vụ của bạn là kiểm tra xem câu hỏi và đáp án được cung cấp có chính xác và được chứng minh bởi nội dung tài liệu nguồn dưới đây hay không.

=== NỘI DUNG TÀI LIỆU NGUỒN (SOURCE CONTEXT) ===
{source_context}

=== CÂU HỎI VÀ ĐÁP ÁN CẦN KIỂM ĐỊNH ===
Câu hỏi: {question}
Đáp án hiện tại: {correct_answer}

=== TIÊU CHÍ ĐÁNH GIÁ ===
1. Đối chiếu kỹ nội dung câu hỏi và đáp án với tài liệu nguồn.
2. Trả lời YES nếu đáp án hiện tại hoàn toàn chính xác và được hỗ trợ rõ ràng bởi tài liệu nguồn.
3. Trả lời NO nếu đáp án hiện tại bị sai, gây hiểu lầm hoặc tài liệu nguồn chỉ ra một đáp án khác.
4. Nếu kết quả là NO, bạn phải xác định đáp án đúng chính xác là gì (A, B, C hoặc D) dựa trên các lựa chọn của câu hỏi và nội dung tài liệu nguồn, đồng thời giải thích rõ ràng căn cứ.

=== ĐỊNH DẠNG ĐẦU RA ===
Chỉ trả về DUY NHẤT một JSON object hợp lệ:
{{
  "verdict": "YES",
  "is_valid": true,
  "correct_answer": "{correct_answer}",
  "explanation": "Giải thích ngắn gọn căn cứ từ tài liệu nguồn..."
}}
(Nếu verdict là "NO", đặt "is_valid": false, "correct_answer": "<ký tự đáp án đúng mới>", và "explanation": "<lý do sai và căn cứ sửa>")
"""

EXPLANATION_GENERATION_PROMPT = """Bạn là giảng viên hướng dẫn học tập tận tâm.
Người học vừa trả lời sai một câu hỏi trắc nghiệm. Nhiệm vụ của bạn là giải thích cặn kẽ tại sao đáp án đúng là chính xác, đồng thời chỉ ra điểm hiểu nhầm trong lựa chọn của người học và trích dẫn tài liệu nguồn.

=== NỘI DUNG TÀI LIỆU NGUỒN (SOURCE CONTEXT) ===
{source_context}

=== THÔNG TIN CÂU HỎI ===
Câu hỏi: {question}
Các lựa chọn:
{options}

Đáp án đúng của hệ thống: {correct_answer}
Câu trả lời của người học: {user_answer}

=== YÊU CẦU GIẢI THÍCH ===
1. Trình bày bằng tiếng Việt rõ ràng, sư phạm, mang tính xây dựng và khích lệ người học.
2. Giải thích rõ ràng tại sao đáp án đúng ({correct_answer}) là chính xác dựa trên tài liệu.
3. Phân tích tại sao lựa chọn của người học ({user_answer}) là chưa chính xác (nếu khác đáp án đúng).
4. Trích dẫn cụ thể câu hoặc đoạn trong tài liệu nguồn làm bằng chứng minh họa.
"""

TOPIC_EXTRACTION_PROMPT = """Bạn là chuyên gia phân tích nội dung và trích xuất thông tin.
Nhiệm vụ của bạn là trích xuất danh sách các nhãn chủ đề (topic labels) quan trọng nhất từ nội dung chương học dưới đây.

=== THÔNG TIN CHƯƠNG HỌC ===
Tiêu đề: {chapter_title}
Nội dung:
{content}

=== YÊU CẦU ===
1. Trích xuất từ 3 đến 8 nhãn chủ đề tiêu biểu nhất phản ánh các khái niệm trọng tâm của chương.
2. Mỗi nhãn chủ đề là một cụm từ ngắn gọn (2-5 từ) bằng tiếng Việt hoặc thuật ngữ chuyên ngành chuẩn xác.
3. Loại bỏ các từ quá chung chung hoặc từ dừng.

=== ĐỊNH DẠNG ĐẦU RA ===
Chỉ trả về DUY NHẤT một JSON array chứa danh sách các chuỗi nhãn chủ đề:
[
  "Chủ đề 1",
  "Chủ đề 2",
  "Chủ đề 3"
]
"""

