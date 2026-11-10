import React from 'react';
import type { QuestionItem } from '../types';

interface QuestionCardProps {
  question: QuestionItem;
  index: number;
  total: number;
  selectedAnswer?: string;
  onSelectAnswer: (answer: string) => void;
}

export const QuestionCard: React.FC<QuestionCardProps> = ({
  question,
  index,
  total,
  selectedAnswer,
  onSelectAnswer,
}) => {
  const getDifficultyBadge = (diff: string) => {
    switch (diff?.toLowerCase()) {
      case 'easy':
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            Dễ
          </span>
        );
      case 'hard':
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            Khó
          </span>
        );
      case 'medium':
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            Trung bình
          </span>
        );
    }
  };

  const optionKeys = ['A', 'B', 'C', 'D'];

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 mb-6 transition-all hover:border-slate-300">
      {/* Header: Index, Difficulty, Topic */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-3 mb-4 border-b border-slate-100">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-bold px-2.5 py-1 rounded-lg bg-blue-50 text-blue-700 border border-blue-100">
            Câu {index + 1} / {total}
          </span>
          {getDifficultyBadge(question.difficulty)}
        </div>

        {question.topic_tag && (
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-lg">
            #{question.topic_tag}
          </span>
        )}
      </div>

      {/* Question Text */}
      <div className="text-base font-semibold text-slate-800 leading-relaxed mb-5">
        {question.question_text}
      </div>

      {/* 4 Options */}
      <div className="space-y-3">
        {optionKeys.map((key) => {
          const optionText = question.options[key] || '';
          const isSelected = selectedAnswer === key;

          return (
            <label
              key={key}
              onClick={() => onSelectAnswer(key)}
              className={`quiz-option flex items-start space-x-3.5 p-3.5 rounded-xl border cursor-pointer select-none transition-all ${
                isSelected
                  ? 'border-blue-500 bg-blue-50/70 text-blue-950 font-medium shadow-xs'
                  : 'border-slate-200 hover:border-blue-300 hover:bg-slate-50/80 text-slate-700'
              }`}
            >
              <div className="pt-0.5 flex-shrink-0">
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={key}
                  checked={isSelected}
                  onChange={() => onSelectAnswer(key)}
                  className="w-4 h-4 text-blue-600 border-slate-300 focus:ring-blue-500 cursor-pointer"
                />
              </div>

              <div className="flex items-baseline space-x-2 flex-1">
                <span
                  className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                    isSelected
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-200 text-slate-600'
                  }`}
                >
                  {key}
                </span>
                <span className="text-sm leading-normal flex-1">
                  {optionText}
                </span>
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
};

export default QuestionCard;
