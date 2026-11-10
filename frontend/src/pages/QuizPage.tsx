import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Clock, Send, AlertCircle, ArrowLeft } from 'lucide-react';
import { submitQuiz } from '../api/quiz';
import type { QuestionItem, QuizAnswerItem } from '../types';
import QuestionCard from '../components/QuestionCard';

export const QuizPage: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const location = useLocation();

  const [questions, setQuestions] = useState<QuestionItem[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [secondsElapsed, setSecondsElapsed] = useState<number>(0);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const timerRef = useRef<any>(null);

  // Initialize questions from location.state or sessionStorage
  useEffect(() => {
    if (!sessionId) return;

    const storageKey = `study_rag_quiz_${sessionId}`;
    const stateQuestions = (location.state as any)?.questions as QuestionItem[] | undefined;

    if (stateQuestions && stateQuestions.length > 0) {
      setQuestions(stateQuestions);
      sessionStorage.setItem(storageKey, JSON.stringify(stateQuestions));
    } else {
      const cached = sessionStorage.getItem(storageKey);
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          setQuestions(parsed);
        } catch {
          // ignore error
        }
      }
    }
  }, [sessionId, location.state]);

  // Timer counter
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setSecondsElapsed((prev) => prev + 1);
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  const formatTime = (totalSeconds: number): string => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSelectAnswer = (questionId: number, answer: string) => {
    setAnswers((prev) => ({
      ...prev,
      [questionId]: answer,
    }));
  };

  const handleSubmit = async () => {
    if (!sessionId || questions.length === 0) return;

    const answeredCount = Object.keys(answers).length;
    const unansweredCount = questions.length - answeredCount;

    if (unansweredCount > 0) {
      const confirmSubmit = window.confirm(
        `Bạn còn ${unansweredCount} câu chưa chọn đáp án. Bạn có chắc chắn muốn nộp bài không?`
      );
      if (!confirmSubmit) return;
    }

    setSubmitting(true);
    setErrorMsg(null);

    // Prepare payload
    const answerItems: QuizAnswerItem[] = Object.entries(answers).map(([qid, ans]) => ({
      question_id: parseInt(qid, 10),
      answer: ans,
    }));

    try {
      const result = await submitQuiz({
        session_id: parseInt(sessionId, 10),
        answers: answerItems,
      });

      // Clear cached session questions
      sessionStorage.removeItem(`study_rag_quiz_${sessionId}`);

      // Navigate to Result Page
      navigate(`/result/${sessionId}`, { state: { result } });
    } catch (err: any) {
      console.error(err);
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Không thể nộp bài. Vui lòng kiểm tra lại kết nối.';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
      setSubmitting(false);
    }
  };

  const scrollToQuestion = (index: number) => {
    const el = document.getElementById(`question-card-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  if (questions.length === 0) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 bg-white rounded-3xl border border-slate-200 p-8 shadow-sm">
        <AlertCircle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-slate-800">Không tìm thấy câu hỏi bài thi</h2>
        <p className="text-xs text-slate-500 mt-2 mb-6">
          Có thể phiên ôn tập đã kết thúc hoặc được tải trực tiếp không qua trang tài liệu.
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

  const answeredCount = Object.keys(answers).length;
  const progressPercent = Math.round((answeredCount / questions.length) * 100);

  return (
    <div className="max-w-3xl mx-auto space-y-6 pb-20 animate-fade-in">
      {/* Sticky Top Status & Timer Bar */}
      <div className="sticky top-20 z-40 bg-white/95 backdrop-blur-md rounded-2xl border border-slate-200/90 shadow-md p-4 transition-all">
        <div className="flex items-center justify-between gap-4">
          {/* Timer */}
          <div className="flex items-center space-x-2 text-slate-800 font-mono font-bold text-sm bg-slate-100 px-3 py-1.5 rounded-xl border border-slate-200">
            <Clock className="w-4 h-4 text-blue-600" />
            <span>{formatTime(secondsElapsed)}</span>
          </div>

          {/* Progress Stats */}
          <div className="flex-1 max-w-xs hidden sm:block">
            <div className="flex justify-between text-xs font-semibold text-slate-600 mb-1">
              <span>Tiến độ làm bài</span>
              <span>
                {answeredCount}/{questions.length} câu
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Submit Action */}
          <button
            type="button"
            disabled={submitting}
            onClick={handleSubmit}
            className="flex items-center space-x-1.5 px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-xs font-bold rounded-xl shadow-md shadow-blue-500/20 transition-all hover:scale-[1.02]"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{submitting ? 'Đang nộp...' : 'Nộp bài'}</span>
          </button>
        </div>

        {/* Question Navigation Dots */}
        <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-slate-100 justify-center sm:justify-start">
          {questions.map((q, idx) => {
            const isAnswered = answers[q.id] !== undefined;
            return (
              <button
                key={q.id}
                type="button"
                onClick={() => scrollToQuestion(idx)}
                className={`w-7 h-7 rounded-lg text-xs font-bold transition-all ${
                  isAnswered
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
                title={`Chuyển đến câu ${idx + 1}`}
              >
                {idx + 1}
              </button>
            );
          })}
        </div>
      </div>

      {/* Error alert */}
      {errorMsg && (
        <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Questions List */}
      <div>
        {questions.map((question, index) => (
          <div key={question.id} id={`question-card-${index}`}>
            <QuestionCard
              question={question}
              index={index}
              total={questions.length}
              selectedAnswer={answers[question.id]}
              onSelectAnswer={(ans) => handleSelectAnswer(question.id, ans)}
            />
          </div>
        ))}
      </div>

      {/* Bottom Submit Banner */}
      <div className="bg-white rounded-3xl border border-slate-200 p-6 text-center shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h4 className="text-sm font-bold text-slate-800">Hoàn thành bài kiểm tra</h4>
          <p className="text-xs text-slate-500">
            Bạn đã trả lời {answeredCount} / {questions.length} câu hỏi.
          </p>
        </div>

        <button
          type="button"
          disabled={submitting}
          onClick={handleSubmit}
          className="w-full sm:w-auto px-8 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white text-sm font-bold rounded-xl shadow-md shadow-blue-500/20 transition-all"
        >
          {submitting ? 'Đang nộp bài...' : 'Nộp bài ngay'}
        </button>
      </div>
    </div>
  );
};

export default QuizPage;
