import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { ArrowLeft, RotateCcw, Home, CheckCircle2, XCircle } from 'lucide-react';
import { getSession } from '../api/quiz';
import type { QuizResultResponse } from '../types';
import ScoreBoard from '../components/ScoreBoard';
import ExplanationCard from '../components/ExplanationCard';
import LoadingSpinner from '../components/LoadingSpinner';

export const ResultPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [result, setResult] = useState<QuizResultResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [filterMode, setFilterMode] = useState<'all' | 'correct' | 'incorrect'>('all');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchResult = useCallback(async () => {
    if (!sessionId) return;

    // Check if result was passed in navigation state
    const stateResult = (location.state as any)?.result as QuizResultResponse | undefined;
    if (stateResult && stateResult.session_id === parseInt(sessionId, 10)) {
      setResult(stateResult);
      setLoading(false);
      return;
    }

    // Otherwise fetch from backend API
    setLoading(true);
    try {
      const data = await getSession(sessionId);
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setErrorMsg('Không thể tải kết quả bài ôn tập. Có thể phiên chưa hoàn thành.');
    } finally {
      setLoading(false);
    }
  }, [sessionId, location.state]);

  useEffect(() => {
    fetchResult();
  }, [fetchResult]);

  if (loading) {
    return <LoadingSpinner message="Đang tải kết quả bài thi..." />;
  }

  if (errorMsg || !result) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 bg-white rounded-3xl border border-slate-200 p-8 shadow-sm">
        <h2 className="text-xl font-bold text-slate-800">Không tìm thấy kết quả</h2>
        <p className="text-xs text-slate-500 mt-2 mb-6">
          {errorMsg || 'Không tìm thấy thông tin phiên ôn tập này.'}
        </p>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="inline-flex items-center space-x-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-sm"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Về trang chủ</span>
        </button>
      </div>
    );
  }

  const filteredResults = result.results.filter((item) => {
    if (filterMode === 'correct') return item.is_correct;
    if (filterMode === 'incorrect') return !item.is_correct;
    return true;
  });

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-16 animate-fade-in">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          to="/"
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-500 hover:text-blue-600 transition-colors"
        >
          <Home className="w-4 h-4" />
          <span>Trang chủ</span>
        </Link>

        <div className="flex items-center space-x-2">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="flex items-center space-x-1 px-3 py-1.5 rounded-xl border border-slate-200 bg-white text-slate-700 text-xs font-semibold hover:bg-slate-50 transition-colors shadow-xs"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Làm lại / Quay lại</span>
          </button>
        </div>
      </div>

      {/* Score Board with Pure CSS Chart */}
      <ScoreBoard
        score={result.score}
        totalQuestions={result.total_questions}
        correctCount={result.correct_count}
        percentage={result.percentage}
        startedAt={result.started_at}
        finishedAt={result.finished_at}
        mode={result.mode}
      />

      {/* Question Details Header & Filter */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="flex items-center space-x-2 text-sm font-bold text-slate-800">
          <span>Chi tiết từng câu hỏi</span>
          <span className="text-xs text-slate-500 font-normal">
            (Hiển thị {filteredResults.length} / {result.results.length} câu)
          </span>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center space-x-1 bg-slate-100 p-1 rounded-xl">
          <button
            type="button"
            onClick={() => setFilterMode('all')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              filterMode === 'all'
                ? 'bg-white text-slate-800 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            Tất cả ({result.results.length})
          </button>
          <button
            type="button"
            onClick={() => setFilterMode('correct')}
            className={`flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              filterMode === 'correct'
                ? 'bg-white text-emerald-700 shadow-xs'
                : 'text-slate-600 hover:text-emerald-700'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Đúng ({result.correct_count})</span>
          </button>
          <button
            type="button"
            onClick={() => setFilterMode('incorrect')}
            className={`flex items-center space-x-1 px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
              filterMode === 'incorrect'
                ? 'bg-white text-rose-700 shadow-xs'
                : 'text-slate-600 hover:text-rose-700'
            }`}
          >
            <XCircle className="w-3.5 h-3.5" />
            <span>Sai ({result.total_questions - result.correct_count})</span>
          </button>
        </div>
      </div>

      {/* List of Explanation Cards */}
      <div>
        {filteredResults.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-10 text-center text-slate-400 text-sm">
            Không có câu hỏi nào trong danh mục này.
          </div>
        ) : (
          filteredResults.map((item, idx) => (
            <ExplanationCard
              key={item.question_id || idx}
              result={item}
              index={idx}
            />
          ))
        )}
      </div>

      {/* Bottom Navigation */}
      <div className="pt-6 flex justify-center">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-blue-500/20"
        >
          Hoàn thành & Về trang chủ
        </button>
      </div>
    </div>
  );
};

export default ResultPage;
