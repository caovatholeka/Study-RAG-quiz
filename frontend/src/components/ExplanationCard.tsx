import React from 'react';
import { CheckCircle2, XCircle, Info, BookOpen } from 'lucide-react';
import type { DetailedResultItem } from '../types';

interface ExplanationCardProps {
  result: DetailedResultItem;
  index: number;
}

export const ExplanationCard: React.FC<ExplanationCardProps> = ({ result, index }) => {
  const { question_text, options, user_answer, correct_answer, is_correct, explanation } = result;

  const optionKeys = ['A', 'B', 'C', 'D'];

  return (
    <div
      className={`rounded-2xl border p-6 mb-5 transition-all shadow-sm ${
        is_correct
          ? 'bg-white border-emerald-200/80 shadow-emerald-50/50'
          : 'bg-white border-rose-200/80 shadow-rose-50/50'
      }`}
    >
      {/* Header: Question Number & Result Status */}
      <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700">
            Câu {index + 1}
          </span>
          {is_correct ? (
            <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Chính xác</span>
            </span>
          ) : (
            <span className="inline-flex items-center space-x-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800">
              <XCircle className="w-3.5 h-3.5 text-rose-600" />
              <span>Chưa chính xác</span>
            </span>
          )}
        </div>

        <div className="text-xs text-slate-500">
          Bạn chọn:{' '}
          <span
            className={`font-bold px-2 py-0.5 rounded ${
              is_correct
                ? 'bg-emerald-100 text-emerald-800'
                : 'bg-rose-100 text-rose-800'
            }`}
          >
            {user_answer || 'Chưa trả lời'}
          </span>
        </div>
      </div>

      {/* Question prompt */}
      <div className="text-base font-semibold text-slate-800 leading-relaxed mb-4">
        {question_text}
      </div>

      {/* 4 Options Display */}
      <div className="space-y-2.5 mb-5">
        {optionKeys.map((key) => {
          const optText = options[key] || '';
          const isUserChoice = user_answer === key;
          const isCorrectChoice = correct_answer === key;

          let containerClass = 'border-slate-200 bg-slate-50/50 text-slate-700';
          let badgeClass = 'bg-slate-200 text-slate-600';

          if (isCorrectChoice) {
            containerClass = 'border-emerald-500 bg-emerald-50/70 text-emerald-950 font-medium ring-1 ring-emerald-400';
            badgeClass = 'bg-emerald-600 text-white';
          } else if (isUserChoice && !is_correct) {
            containerClass = 'border-rose-400 bg-rose-50/70 text-rose-950 font-medium';
            badgeClass = 'bg-rose-500 text-white';
          }

          return (
            <div
              key={key}
              className={`flex items-start space-x-3 p-3 rounded-xl border text-sm transition-colors ${containerClass}`}
            >
              <span className={`text-xs font-bold px-2 py-0.5 rounded ${badgeClass}`}>
                {key}
              </span>
              <span className="flex-1">{optText}</span>
              {isCorrectChoice && (
                <span className="text-xs font-semibold text-emerald-700 flex items-center space-x-1">
                  <CheckCircle2 className="w-4 h-4" />
                  <span className="hidden sm:inline">Đáp án đúng</span>
                </span>
              )}
              {isUserChoice && !is_correct && (
                <span className="text-xs font-semibold text-rose-600 flex items-center space-x-1">
                  <XCircle className="w-4 h-4" />
                  <span className="hidden sm:inline">Bạn đã chọn</span>
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Explanation & Source Citation */}
      {explanation && (
        <div className="mt-4 p-4 rounded-xl bg-blue-50/80 border border-blue-100 text-slate-800 space-y-2">
          <div className="flex items-center space-x-1.5 text-xs font-bold text-blue-800 uppercase tracking-wider">
            <Info className="w-4 h-4 text-blue-600" />
            <span>Giải thích & Phân tích đáp án</span>
          </div>
          <p className="text-sm text-slate-700 leading-relaxed pl-5">
            {explanation}
          </p>

          {/* Trích dẫn nguồn nếu có thông tin trích dẫn hoặc chapter */}
          <div className="pt-2 pl-5 flex items-center space-x-1 text-xs text-blue-600 font-medium">
            <BookOpen className="w-3.5 h-3.5 flex-shrink-0" />
            <span>Nguồn tài liệu: Trích xuất từ tài liệu học tập qua mô hình RAG</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default ExplanationCard;
