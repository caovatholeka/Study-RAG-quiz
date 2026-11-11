import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  Play,
  AlertCircle,
  CheckCircle2,
  Calendar,
  Settings2,
} from 'lucide-react';
import { getDocument } from '../api/documents';
import { getChapters } from '../api/chapters';
import { generateQuiz, startQuiz, getQuizStats, type QuizStatsResponse } from '../api/quiz';
import type { DocumentItem, ChapterItem } from '../types';
import ChapterTree from '../components/ChapterTree';
import LoadingSpinner from '../components/LoadingSpinner';

export const DocumentPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [chapters, setChapters] = useState<ChapterItem[]>([]);
  const [selectedChapterIds, setSelectedChapterIds] = useState<number[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [startingQuiz, setStartingQuiz] = useState<boolean>(false);
  const [numQuestions, setNumQuestions] = useState<number>(5);
  const [quizMode, setQuizMode] = useState<string>('chapter');
  const [quizStats, setQuizStats] = useState<QuizStatsResponse | null>(null);

  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error' | 'info';
    message: string;
  } | null>(null);

  const fetchData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [docData, chapData, statsData] = await Promise.all([
        getDocument(id),
        getChapters(id),
        getQuizStats(id).catch(() => null),
      ]);
      setDocument(docData);
      setChapters(chapData.chapters || []);
      if (statsData) {
        setQuizStats(statsData);
        if (statsData.is_generating) {
          setGenerating(true);
        }
      }

      // Default select all chapters
      const extractIds = (items: ChapterItem[]): number[] => {
        let ids: number[] = [];
        items.forEach((item) => {
          ids.push(item.id);
          if (item.children) ids = ids.concat(extractIds(item.children));
        });
        return ids;
      };
      const allIds = extractIds(chapData.chapters || []);
      setSelectedChapterIds(allIds);
    } catch (err: any) {
      console.error(err);
      setFeedback({
        type: 'error',
        message: 'Không thể tải thông tin tài liệu. Vui lòng thử lại.',
      });
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Polling tiến trình sinh câu hỏi nền (kể cả khi chuyển tab rồi quay lại)
  useEffect(() => {
    if (!id || !generating) return;

    const interval = setInterval(async () => {
      try {
        const stats = await getQuizStats(id);
        setQuizStats(stats);
        if (!stats.is_generating) {
          setGenerating(false);
          setFeedback({
            type: 'success',
            message: `Hoàn tất! Ngân hàng câu hỏi hiện có ${stats.total_questions} câu hỏi được lưu trong CSDL SQLite. Bạn có thể bắt đầu làm bài ngay!`,
          });
        }
      } catch (err) {
        console.error('Lỗi polling quiz stats:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [id, generating]);

  const handleToggleSelect = (chapterId: number) => {
    setSelectedChapterIds((prev) =>
      prev.includes(chapterId)
        ? prev.filter((i) => i !== chapterId)
        : [...prev, chapterId]
    );
  };

  const handleSelectAll = (ids: number[]) => {
    setSelectedChapterIds(ids);
  };

  const handleDeselectAll = () => {
    setSelectedChapterIds([]);
  };

  const handleGenerateQuiz = async () => {
    if (!id) return;
    setGenerating(true);
    setFeedback(null);
    try {
      // Gửi đúng số lượng câu hỏi numQuestions được chọn lên backend
      const res = await generateQuiz(id, numQuestions);
      setFeedback({
        type: 'info',
        message: res.message || `Hệ thống AI đang bắt đầu sinh ${numQuestions} câu hỏi cho tài liệu trong background...`,
      });
      const stats = await getQuizStats(id);
      setQuizStats(stats);
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        'Không thể tạo câu hỏi. Hãy đảm bảo tài liệu đã ở trạng thái Sẵn sàng.';
      setFeedback({
        type: 'error',
        message: typeof msg === 'string' ? msg : JSON.stringify(msg),
      });
      setGenerating(false);
    }
  };

  const handleStartQuiz = async () => {
    if (selectedChapterIds.length === 0) {
      setFeedback({
        type: 'error',
        message: 'Vui lòng chọn ít nhất 1 chương để bắt đầu bài ôn tập!',
      });
      return;
    }

    setStartingQuiz(true);
    setFeedback(null);
    try {
      const res = await startQuiz({
        chapter_ids: selectedChapterIds,
        num_questions: numQuestions,
        mode: quizMode,
      });

      if (res && res.session_id) {
        navigate(`/quiz/${res.session_id}`, { state: { questions: res.questions } });
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string' && detail.includes('Chưa có câu hỏi')) {
        setFeedback({
          type: 'info',
          message: 'Tài liệu này chưa có ngân hàng câu hỏi. Hãy nhấn nút "Tạo câu hỏi" để AI sinh câu hỏi trước!',
        });
      } else {
        setFeedback({
          type: 'error',
          message: detail || 'Không thể bắt đầu phiên ôn tập. Vui lòng thử lại.',
        });
      }
    } finally {
      setStartingQuiz(false);
    }
  };

  if (loading) {
    return <LoadingSpinner message="Đang tải dữ liệu tài liệu..." />;
  }

  if (!document) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-600 mb-4">Không tìm thấy tài liệu.</p>
        <Link
          to="/"
          className="inline-flex items-center space-x-1.5 px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Quay lại trang chủ</span>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top back navigation & title */}
      <div>
        <Link
          to="/"
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-blue-600 mb-3 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Quay lại danh sách tài liệu</span>
        </Link>

        <div className="bg-white rounded-3xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-700 uppercase">
                {document.file_type}
              </span>
              <span className="text-xs text-slate-400 flex items-center space-x-1">
                <Calendar className="w-3.5 h-3.5" />
                <span>
                  {new Date(document.created_at).toLocaleDateString('vi-VN')}
                </span>
              </span>
            </div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-800">
              {document.original_filename}
            </h1>
            <p className="text-xs text-slate-500">
              Tài liệu gồm {chapters.length} chương / đề mục chính đã được phân tích
            </p>
          </div>

          {/* Quick Actions Header */}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={generating}
              onClick={handleGenerateQuiz}
              className="flex items-center space-x-1.5 px-4 py-2.5 rounded-xl border border-blue-200 bg-blue-50 hover:bg-blue-100 text-blue-700 text-xs font-bold transition-all shadow-xs disabled:opacity-50"
            >
              <Sparkles className={`w-4 h-4 ${generating ? 'animate-spin' : ''}`} />
              <span>{generating ? 'Đang tạo câu hỏi...' : `Tạo ${numQuestions} câu hỏi bằng AI`}</span>
            </button>

            <button
              type="button"
              disabled={startingQuiz || selectedChapterIds.length === 0}
              onClick={handleStartQuiz}
              className="flex items-center space-x-1.5 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white text-xs font-bold transition-all shadow-md shadow-blue-500/20"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>
                {startingQuiz
                  ? 'Đang khởi tạo...'
                  : `Bắt đầu ôn tập (${quizStats?.total_questions || 0} câu có sẵn)`}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Banner Trạng thái Ngân hàng Câu hỏi & Tiến trình Sinh câu hỏi */}
      <div className="bg-white rounded-3xl border border-slate-200 p-5 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center space-x-3.5">
            <div
              className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                generating
                  ? 'bg-blue-100 text-blue-600 animate-pulse'
                  : (quizStats?.total_questions || 0) > 0
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-amber-100 text-amber-700'
              }`}
            >
              {generating ? (
                <Sparkles className="w-6 h-6 animate-spin" />
              ) : (quizStats?.total_questions || 0) > 0 ? (
                <CheckCircle2 className="w-6 h-6 text-emerald-600" />
              ) : (
                <AlertCircle className="w-6 h-6 text-amber-600" />
              )}
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-bold text-slate-800">
                  Ngân hàng câu hỏi trắc nghiệm
                </h2>
                <span className="text-[11px] px-2.5 py-0.5 rounded-full font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Đã lưu trong CSDL SQLite
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {generating
                  ? (quizStats?.progress_message || 'AI đang sinh và xác thực câu hỏi theo tài liệu...')
                  : (quizStats?.total_questions || 0) > 0
                  ? `Đã lưu vĩnh viễn ${quizStats?.total_questions} câu hỏi vào CSDL. Mở lại ứng dụng sau này vẫn còn nguyên 100%.`
                  : 'Tài liệu này chưa có câu hỏi nào trong CSDL. Bạn hãy nhấn nút "Tạo câu hỏi bằng AI" để AI sinh bộ đề.'}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3 self-end sm:self-center">
            <div className="text-right">
              <span className="text-2xl font-black text-blue-600 block leading-tight">
                {quizStats?.total_questions || 0}
              </span>
              <span className="text-[11px] text-slate-400 font-medium">câu hỏi sẵn sàng</span>
            </div>
          </div>
        </div>

        {/* Thanh tiến trình chạy trực tiếp khi đang sinh câu hỏi */}
        {generating && (
          <div className="mt-4 pt-3 border-t border-slate-100 space-y-2">
            <div className="flex items-center justify-between text-xs text-blue-700 font-semibold">
              <span className="flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
                <span>{quizStats?.progress_message || 'Đang tạo câu hỏi trong background...'}</span>
              </span>
              <span>Đang lưu vào CSDL...</span>
            </div>
            <div className="w-full bg-blue-50 h-2.5 rounded-full overflow-hidden border border-blue-100">
              <div className="bg-gradient-to-r from-blue-500 to-indigo-600 h-full rounded-full animate-pulse w-4/5 transition-all duration-700" />
            </div>
          </div>
        )}
      </div>

      {/* Notifications */}
      {feedback && (
        <div
          className={`p-4 rounded-2xl border text-sm flex items-center space-x-2.5 animate-fade-in ${
            feedback.type === 'success'
              ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
              : feedback.type === 'info'
              ? 'bg-blue-50 border-blue-200 text-blue-800'
              : 'bg-rose-50 border-rose-200 text-rose-800'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
          )}
          <span className="font-medium flex-1">{feedback.message}</span>
        </div>
      )}

      {/* Main Grid: Quiz Setup + Chapter Tree */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left column: Quiz Configuration Panel */}
        <div className="lg:col-span-4 space-y-5">
          <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm space-y-4">
            <div className="flex items-center space-x-2 pb-2 border-b border-slate-100 text-slate-800 font-bold text-sm">
              <Settings2 className="w-4 h-4 text-blue-600" />
              <span>Cấu hình ôn tập</span>
            </div>

            {/* Số câu hỏi */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Số lượng câu hỏi
              </label>
              <div className="grid grid-cols-4 gap-1.5">
                {[5, 10, 15, 20].map((num) => (
                  <button
                    key={num}
                    type="button"
                    onClick={() => setNumQuestions(num)}
                    className={`py-2 text-xs font-bold rounded-xl border transition-all ${
                      numQuestions === num
                        ? 'border-blue-600 bg-blue-600 text-white shadow-xs'
                        : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                    }`}
                  >
                    {num} câu
                  </button>
                ))}
              </div>
            </div>

            {/* Chế độ làm bài */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Chế độ ôn tập
              </label>
              <div className="space-y-2">
                <label
                  onClick={() => setQuizMode('chapter')}
                  className={`flex items-start space-x-2.5 p-2.5 rounded-xl border cursor-pointer text-xs transition-all ${
                    quizMode === 'chapter'
                      ? 'border-blue-500 bg-blue-50 text-blue-900 font-semibold'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="quiz-mode"
                    checked={quizMode === 'chapter'}
                    onChange={() => setQuizMode('chapter')}
                    className="mt-0.5 text-blue-600"
                  />
                  <div>
                    <div>Theo chương đã chọn</div>
                    <div className="text-[11px] text-slate-400 font-normal mt-0.5">
                      Lấy câu hỏi thuộc các chương được tích chọn
                    </div>
                  </div>
                </label>

                <label
                  onClick={() => setQuizMode('full')}
                  className={`flex items-start space-x-2.5 p-2.5 rounded-xl border cursor-pointer text-xs transition-all ${
                    quizMode === 'full'
                      ? 'border-blue-500 bg-blue-50 text-blue-900 font-semibold'
                      : 'border-slate-200 text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  <input
                    type="radio"
                    name="quiz-mode"
                    checked={quizMode === 'full'}
                    onChange={() => setQuizMode('full')}
                    className="mt-0.5 text-blue-600"
                  />
                  <div>
                    <div>Toàn bộ tài liệu</div>
                    <div className="text-[11px] text-slate-400 font-normal mt-0.5">
                      Ngẫu nhiên các câu hỏi từ tất cả các chương
                    </div>
                  </div>
                </label>
              </div>
            </div>

            <button
              type="button"
              disabled={
                startingQuiz ||
                selectedChapterIds.length === 0 ||
                (quizStats?.total_questions || 0) === 0
              }
              onClick={handleStartQuiz}
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white rounded-xl text-xs font-bold flex items-center justify-center space-x-2 shadow-sm transition-all"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>
                {startingQuiz
                  ? 'Đang chuẩn bị đề...'
                  : (quizStats?.total_questions || 0) === 0
                  ? 'Chưa có câu hỏi (Hãy tạo bằng AI trước)'
                  : `Bắt đầu làm bài (${Math.min(numQuestions, quizStats?.total_questions || 0)}/${numQuestions} câu)`}
              </span>
            </button>
          </div>
        </div>

        {/* Right column: Hierarchical Chapter Tree */}
        <div className="lg:col-span-8">
          <ChapterTree
            chapters={chapters}
            selectedIds={selectedChapterIds}
            onToggleSelect={handleToggleSelect}
            onSelectAll={handleSelectAll}
            onDeselectAll={handleDeselectAll}
            onViewChapter={(chap) => navigate(`/chapter/${chap.id}`)}
          />
        </div>
      </div>
    </div>
  );
};

export default DocumentPage;
