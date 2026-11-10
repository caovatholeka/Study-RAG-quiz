import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, BookOpen, Play, Tag, AlertCircle } from 'lucide-react';
import { getChapter } from '../api/chapters';
import { startQuiz } from '../api/quiz';
import type { ChapterDetailResponse } from '../types';
import LoadingSpinner from '../components/LoadingSpinner';

export const ChapterPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [chapter, setChapter] = useState<ChapterDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [startingQuiz, setStartingQuiz] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchChapter = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const data = await getChapter(id);
      setChapter(data);
    } catch (err: any) {
      console.error(err);
      setErrorMessage('Không thể tải nội dung chương. Vui lòng thử lại.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchChapter();
  }, [fetchChapter]);

  const handleStartChapterQuiz = async () => {
    if (!chapter) return;
    setStartingQuiz(true);
    setErrorMessage(null);

    try {
      const res = await startQuiz({
        chapter_ids: [chapter.id],
        mode: 'chapter',
        num_questions: 10,
      });

      if (res && res.session_id) {
        navigate(`/quiz/${res.session_id}`, { state: { questions: res.questions } });
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setErrorMessage(
        detail ||
          'Chưa có câu hỏi cho chương này. Vui lòng quay lại tài liệu và bấm "Tạo câu hỏi bằng AI" trước.'
      );
    } finally {
      setStartingQuiz(false);
    }
  };

  if (loading) {
    return <LoadingSpinner message="Đang tải nội dung chương..." />;
  }

  if (!chapter) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-600 mb-4">Không tìm thấy thông tin chương.</p>
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Quay lại</span>
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-fade-in">
      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => navigate(`/document/${chapter.document_id}`)}
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-blue-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Quay lại tài liệu</span>
        </button>

        <button
          type="button"
          disabled={startingQuiz}
          onClick={handleStartChapterQuiz}
          className="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white text-xs font-bold rounded-xl shadow-md shadow-blue-500/20 transition-all"
        >
          <Play className="w-3.5 h-3.5 fill-white" />
          <span>{startingQuiz ? 'Đang khởi tạo...' : 'Ôn tập chương này'}</span>
        </button>
      </div>

      {errorMessage && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Chapter Header Card */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs">
        <div className="flex items-center space-x-2 text-xs font-bold text-blue-600 mb-2">
          <span className="px-2.5 py-1 bg-blue-50 rounded-lg border border-blue-100">
            Chương {chapter.chapter_number}
          </span>
          {chapter.level && (
            <span className="px-2.5 py-1 bg-slate-100 text-slate-600 rounded-lg">
              Cấp độ: {chapter.level}
            </span>
          )}
          {chapter.page_start && (
            <span className="text-slate-400 font-normal">
              Trang {chapter.page_start}
              {chapter.page_end ? ` - ${chapter.page_end}` : ''}
            </span>
          )}
        </div>

        <h1 className="text-2xl font-extrabold text-slate-800 tracking-tight mb-4">
          {chapter.title}
        </h1>

        {/* Topic tags if present */}
        {chapter.topic_labels && Array.isArray(chapter.topic_labels) && chapter.topic_labels.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-slate-100">
            <Tag className="w-3.5 h-3.5 text-slate-400" />
            {chapter.topic_labels.map((tag: string, idx: number) => (
              <span
                key={idx}
                className="px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md text-[11px] font-medium"
              >
                #{tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Chapter Text Content Card */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 sm:p-8 shadow-xs space-y-4">
        <div className="flex items-center space-x-2 text-slate-800 font-bold text-base pb-3 border-b border-slate-100">
          <BookOpen className="w-5 h-5 text-blue-600" />
          <span>Nội dung chi tiết</span>
        </div>

        {chapter.content ? (
          <div className="prose max-w-none text-slate-700 leading-relaxed text-sm whitespace-pre-line font-sans">
            {chapter.content}
          </div>
        ) : (
          <div className="py-12 text-center text-slate-400 text-sm">
            Nội dung chương này chưa có văn bản chi tiết hoặc đang được phân tích.
          </div>
        )}
      </div>
    </div>
  );
};

export default ChapterPage;
