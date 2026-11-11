# -*- coding: utf-8 -*-
"""
Script kiểm tra kết nối LLM API Key (OpenAI hoặc Google Gemini) và tính năng sinh câu hỏi trắc nghiệm của StudyRAG.
Tự động nhận diện nhà cung cấp:
    - OpenAI: API Key bắt đầu bằng "sk-" (mặc định gpt-4o-mini)
    - Google Gemini: API Key bắt đầu bằng "AIza" hoặc "AQ." (mặc định gemini-2.0-flash / gemini-1.5-flash)

Sử dụng:
    python test_gemini_key.py
hoặc:
    python test_gemini_key.py --key sk-proj-YourOpenAIKey...
    python test_gemini_key.py --key AIzaSyYourGeminiKey...
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Thêm thư mục backend vào sys.path
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir / "backend" if (current_dir / "backend" / "app").exists() else current_dir
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config import settings
from app.services.quiz_generator import QuizGenerator


def mask_key(key: str) -> str:
    """Ẩn bớt ký tự API key để bảo mật khi in ra màn hình."""
    if not key or len(key) < 10:
        return "***"
    return f"{key[:7]}...{key[-4:]}"


def save_key_to_env(key: str, provider: str = "auto"):
    """Lưu API key vào các file .env trong project."""
    env_paths = [
        backend_dir / ".env",
        backend_dir.parent / ".env",
    ]
    key_var = "OPENAI_API_KEY" if (provider == "openai" or key.startswith("sk-")) else "GEMINI_API_KEY"

    for p in env_paths:
        try:
            content = ""
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    content = f.read()

            if f"{key_var}=" in content:
                import re
                content = re.sub(rf"{key_var}=.*", f"{key_var}={key}", content)
            else:
                content += f"\n{key_var}={key}\n"

            if key_var == "OPENAI_API_KEY":
                if "LLM_PROVIDER=" in content:
                    import re
                    content = re.sub(r"LLM_PROVIDER=.*", "LLM_PROVIDER=openai", content)
                else:
                    content += "\nLLM_PROVIDER=openai\n"

            with open(p, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  -> Đã lưu API key vào: {p.resolve()}")
        except Exception as e:
            print(f"  -> Không thể ghi vào {p}: {e}")


def test_openai_api(api_key: str, model_name: str) -> tuple[bool, str]:
    """Kiểm tra gọi OpenAI Chat Completions API."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "Xin chào, hãy phản hồi 'OK'!"}],
            max_tokens=15,
            temperature=0.2,
        )
        reply = resp.choices[0].message.content.strip() if resp.choices else "OK"
        return True, reply
    except Exception as e:
        return False, str(e)


def test_gemini_rest_api(api_key: str, model_name: str) -> tuple[bool, str]:
    """Kiểm tra gọi trực tiếp qua REST API với header x-goog-api-key."""
    import requests

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "contents": [{"parts": [{"text": "Xin chào, hãy phản hồi 'OK'!"}]}]
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            data = r.json()
            candidates = data.get("candidates", [])
            txt = candidates[0]["content"]["parts"][0]["text"] if candidates else "OK"
            return True, txt.strip()
        else:
            return False, f"Status {r.status_code}: {r.text[:250]}"
    except Exception as e:
        return False, str(e)


def test_gemini_sdk(api_key: str, model_name: str) -> tuple[bool, str]:
    """Kiểm tra gọi qua google-genai SDK v3."""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents="Xin chào, hãy phản hồi 'OK'!",
        )
        txt = response.text.strip() if response and response.text else "OK"
        return True, txt
    except Exception as e:
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Kiểm thử LLM API Key cho StudyRAG")
    parser.add_argument("--key", type=str, help="API Key cần kiểm tra (OpenAI hoặc Google Gemini)")
    parser.add_argument("--model", type=str, default=None, help="Tên model (gpt-4o-mini, gemini-2.0-flash,...)")
    parser.add_argument("--provider", type=str, default=None, help="Nhà cung cấp: openai hoặc gemini")
    args = parser.parse_args()

    # Xác định API key
    api_key = args.key
    provider_arg = (args.provider or "").lower()

    if not api_key:
        if provider_arg == "openai":
            api_key = getattr(settings, "OPENAI_API_KEY", "")
        elif provider_arg == "gemini":
            api_key = getattr(settings, "GEMINI_API_KEY", "") or getattr(settings, "GOOGLE_API_KEY", "")
        else:
            # Tự động lấy OpenAI trước hoặc Gemini
            api_key = (
                getattr(settings, "OPENAI_API_KEY", "")
                or getattr(settings, "GEMINI_API_KEY", "")
                or getattr(settings, "GOOGLE_API_KEY", "")
            )

    if not api_key:
        print("\n" + "=" * 65)
        print("      STUDYRAG - KIỂM THỬ KẾT NỐI LLM API KEY")
        print("=" * 65 + "\n")
        print("[!] Chưa tìm thấy API Key (OpenAI hoặc Gemini) trong file .env.")
        try:
            user_input = input(">> Dán OpenAI Key (sk-...) hoặc Gemini Key vào đây: ").strip()
            if user_input:
                api_key = user_input.strip().strip('"').strip("'")
                save_key_to_env(api_key)
            else:
                print("Chưa có API key. Vui lòng mở file backend/.env và điền key.")
                return 1
        except (KeyboardInterrupt, EOFError):
            print("\nĐã hủy thao tác.")
            return 1

    clean_key = api_key.strip().strip('"').strip("'")

    # Xác định provider
    if provider_arg in ("openai", "gemini"):
        provider = provider_arg
    elif clean_key.startswith("sk-"):
        provider = "openai"
    elif clean_key.startswith("AIza") or clean_key.startswith("AQ."):
        provider = "gemini"
    else:
        provider = getattr(settings, "LLM_PROVIDER", "auto").lower()
        if provider not in ("openai", "gemini"):
            provider = "openai" if clean_key.startswith("sk-") else "gemini"

    provider_name = "OPENAI" if provider == "openai" else "GOOGLE GEMINI"

    print("\n" + "=" * 65)
    print(f"      STUDYRAG - KIỂM THỬ KẾT NỐI {provider_name} API KEY")
    print("=" * 65 + "\n")

    print(f"[*] Nhà cung cấp: {provider_name}")
    print(f"[*] API Key đã nạp: {mask_key(clean_key)} (Độ dài: {len(clean_key)} ký tự)")

    connected = False
    active_model = ""
    success_method = ""
    last_error = ""

    # === NHÁNH OPENAI ===
    if provider == "openai":
        target_model = args.model or getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
        print(f"[*] Mô hình mục tiêu: {target_model}")
        print("[*] Đang kiểm tra kết nối tới OpenAI API...")

        ok_openai, msg_openai = test_openai_api(clean_key, target_model)
        if ok_openai:
            connected = True
            success_method = "OpenAI Python SDK"
            active_model = target_model
            print(f"      -> Thành công qua OpenAI SDK: \"{msg_openai}\"")
        else:
            last_error = msg_openai

    # === NHÁNH GOOGLE GEMINI ===
    else:
        target_model = args.model or getattr(settings, "LLM_MODEL", "gemini-2.0-flash")
        print(f"[*] Mô hình mục tiêu: {target_model}")
        print("[*] Đang kiểm tra qua các phương thức kết nối chuẩn của Google...")

        test_models = [target_model]
        for m in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]:
            if m not in test_models:
                test_models.append(m)

        for m in test_models:
            print(f"  [+] Thử nghiệm với mô hình '{m}'...")

            # 1. Thử qua REST API với header chuẩn x-goog-api-key
            ok_rest, msg_rest = test_gemini_rest_api(clean_key, m)
            if ok_rest:
                connected = True
                success_method = "REST API (Header: x-goog-api-key)"
                active_model = m
                print(f"      -> Thành công qua REST API: \"{msg_rest}\"")
                break
            else:
                last_error = msg_rest

            # 2. Thử qua google-genai SDK
            ok_sdk, msg_sdk = test_gemini_sdk(clean_key, m)
            if ok_sdk:
                connected = True
                success_method = "google-genai SDK"
                active_model = m
                print(f"      -> Thành công qua google-genai SDK: \"{msg_sdk}\"")
                break
            else:
                last_error = msg_sdk

    if not connected:
        print(f"\n[X] Bước 1/2: Kết nối {provider_name} API thất bại!")
        print(f"    Chi tiết phản hồi từ máy chủ:")
        print(f"    {last_error}\n")
        print("    👉 NGUYÊN NHÂN & CÁCH KHẮC PHỤC:")
        if provider == "openai":
            print("    - Kiểm tra xem API Key của OpenAI có còn số dư (balance / credits) hay không.")
            print("    - Kiểm tra xem key có bị thu hồi trên https://platform.openai.com/api-keys hay không.")
        elif "API_KEY_SERVICE_BLOCKED" in last_error or "403" in last_error or "PERMISSION_DENIED" in last_error:
            print("    [!] LỖI 403: API_KEY_SERVICE_BLOCKED (Google đã nhận diện đúng Key, nhưng dịch vụ Gemini bị khóa)")
            print("    Nguyên nhân: Key này nằm trong Google Cloud Project có bật 'Hạn chế API' (API restrictions)")
            print("    nhưng CHƯA tích chọn 'Generative Language API', hoặc API này chưa được bật (Enable) trong project.")
            print("")
            print("    👉 CÁCH KHẮC PHỤC 1 (Nhanh nhất - Tạo key mở từ Google AI Studio):")
            print("       1. Truy cập: https://aistudio.google.com/app/apikey")
            print("       2. Bấm nút 'Create API key' -> Chọn 'Create API key in NEW project'.")
            print("       3. Copy key mới và dán vào file .env.")
            print("")
            print("    👉 CÁCH KHẮC PHỤC 2 (Mở khóa key hiện tại trên Google Cloud Console):")
            print("       1. Vào: https://console.cloud.google.com/apis/credentials")
            print("       2. Bấm vào tên key này, cuộn xuống mục 'API restrictions' (Hạn chế API).")
            print("       3. Chọn 'Don't restrict key' (Không hạn chế khóa), HOẶC tích thêm 'Generative Language API'.")
            print("       4. Đồng thời bật API tại: https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com")
            print("       5. Bấm 'Save' (Lưu) và đợi khoảng 1-2 phút.")
        elif "ACCESS_TOKEN_TYPE_UNSUPPORTED" in last_error or "401" in last_error or "API key not valid" in last_error:
            print("    1. Key bị Google từ chối xác thực (Mã 401 UNAUTHENTICATED).")
            print("    2. Giải pháp:")
            print("       - Vào https://aistudio.google.com/app/apikey bằng Gmail cá nhân.")
            print("       - Bấm 'Create API key' -> Chọn 'Create API key in NEW project'.")
            print("       - Copy và dán lại vào file .env.")
        return 1

    print(f"\n[OK] Bước 1/2: Kết nối {provider_name} API thành công qua {success_method} (Model: {active_model})!")

    # Bước 2: Test sinh câu hỏi trắc nghiệm qua QuizGenerator
    print(f"\n[*] Đang kiểm tra Bước 2/2: Sinh câu hỏi trắc nghiệm tự động (QuizGenerator với {provider_name})...")
    generator = QuizGenerator(api_key=clean_key, provider=provider, model=active_model)
    sample_content = (
        "Kiến trúc RAG (Retrieval-Augmented Generation) là một kỹ thuật nâng cao kết hợp giữa "
        "truy xuất thông tin từ cơ sở dữ liệu vector (như ChromaDB) và mô hình ngôn ngữ lớn (LLM). "
        "RAG giúp giảm thiểu hiện tượng ảo giác (hallucination), cung cấp câu trả lời có trích dẫn nguồn "
        "chính xác từ tài liệu của người dùng mà không cần huấn luyện lại mô hình."
    )

    try:
        questions = generator.generate_questions(
            chapter_title="Tổng quan về RAG",
            chapter_content=sample_content,
            num_questions=1,
        )

        if not questions:
            print(f"[!] Không nhận được câu hỏi hợp lệ từ {provider_name}. Vui lòng thử lại.")
            return 1

        q = questions[0]
        print(f"[OK] Bước 2/2: Sinh câu hỏi trắc nghiệm thành công!")
        print("\n" + "-" * 55)
        print(f"CÂU HỎI MẪU ĐƯỢC SINH TỰ ĐỘNG BỞI {provider_name}:")
        print(f"❓ Câu hỏi: {q.get('question')}")
        print("📋 Các phương án:")
        opts = q.get("options", {})
        for opt_key in sorted(opts.keys()):
            marker = " ✅" if opt_key == q.get("correct_answer") else ""
            print(f"   [{opt_key}] {opts[opt_key]}{marker}")
        print(f"🎯 Đáp án đúng: {q.get('correct_answer')}")
        print(f"📊 Độ khó:     {q.get('difficulty')}")
        print(f"💡 Giải thích:  {q.get('explanation')}")
        if q.get("topic_tag"):
            print(f"🏷️  Chủ đề:     {q.get('topic_tag')}")
        print("-" * 55)

        print("\n" + "=" * 65)
        print("🎉 TẤT CẢ KIỂM THỬ ĐÃ HOÀN TẤT THÀNH CÔNG!")
        print(f"Nhà cung cấp: {provider_name} | Mô hình: {active_model} ({success_method})")
        print("Hệ thống đã sẵn sàng 100% để tạo câu hỏi trắc nghiệm từ tài liệu của bạn!")
        print("=" * 65 + "\n")
        return 0

    except Exception as e:
        print(f"\n[X] Bước 2/2: Lỗi khi sinh câu hỏi: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
