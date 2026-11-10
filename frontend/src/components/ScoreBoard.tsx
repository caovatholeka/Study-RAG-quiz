import React from 'react';
import { Award, CheckCircle2, Percent, Clock } from 'lucide-react';

interface ScoreBoardProps {
  score: number; // e.g. 8.0 (scale 0-10)
  totalQuestions: number;
  correctCount: number;
  percentage: number;
  startedAt?: string;
  finishedAt?: string;
  mode?: string;
}

export const ScoreBoard: React.FC<ScoreBoardProps> = ({
  score,
  totalQuestions,
  correctCount,
  percentage,
  startedAt,
  finishedAt,
  mode = 'chapter',
}) => {
  const incorrectCount = Math.max(0, totalQuestions - correctCount);

  // Time elapsed calculation
  const calculateDuration = (): string => {
    if (!startedAt || !finishedAt) return 'N/A';
    const start = new Date(startedAt).getTime();
    const end = new Date(finishedAt).getTime();
    const diffSec = Math.max(0, Math.floor((end - start) / 1000));
    const mins = Math.floor(diffSec / 60);
    const secs = diffSec % 60;
    if (mins > 0) {
      return `${mins} phút ${secs} giây`;
    }
    return `${secs} giây`;
  };

  const getPerformanceMessage = (pct: number) => {
    if (pct >= 90) return { title: 'Xuất sắc! 🎉', desc: 'Bạn đã nắm rất vững kiến thức phần này!', color: 'text-emerald-600' };
    if (pct >= 75) return { title: 'Làm rất tốt! 👏', desc: 'Kiến thức khá chắc, hãy ôn thêm các câu sai nhé.', color: 'text-blue-600' };
    if (pct >= 50) return { title: 'Đạt yêu cầu 👍', desc: 'Bạn đã hiểu các ý chính nhưng cần rèn luyện thêm.', color: 'text-amber-600' };
    return { title: 'Cần cố gắng thêm 💪', desc: 'Hãy xem lại bài giảng và làm lại bài kiểm tra nhé.', color: 'text-rose-600' };
  };

  const perf = getPerformanceMessage(percentage);

  // Pure CSS circle conic gradient calculation:
  // green: 0% -> percentage%, red: percentage% -> 100%
  const chartStyle = {
    background: `conic-gradient(#10B981 0% ${percentage}%, #EF4444 ${percentage}% 100%)`,
  };

  return (
    <div className="bg-white rounded-3xl border border-slate-200 shadow-md p-6 sm:p-8 mb-8 animate-fade-in">
      <div className="grid grid-cols-1 md:grid-cols-12 gap-8 items-center">
        {/* Left: Pure CSS Donut/Circular Chart */}
        <div className="md:col-span-4 flex flex-col items-center justify-center">
          <div className="relative w-44 h-44 rounded-full flex items-center justify-center shadow-inner" style={chartStyle}>
            {/* Inner white circle for donut effect */}
            <div className="w-32 h-32 bg-white rounded-full flex flex-col items-center justify-center shadow-sm">
              <span className="text-3xl font-extrabold text-slate-800 tracking-tight">
                {score.toFixed(1)}
              </span>
              <span className="text-xs font-semibold text-slate-400">/ 10 điểm</span>
            </div>
          </div>

          <div className="mt-4 flex items-center space-x-4 text-xs font-medium">
            <div className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
              <span className="text-slate-600">Đúng: {correctCount}</span>
            </div>
            <div className="flex items-center space-x-1.5">
              <span className="w-3 h-3 rounded-full bg-rose-500 inline-block" />
              <span className="text-slate-600">Sai: {incorrectCount}</span>
            </div>
          </div>
        </div>

        {/* Right: Detailed Summary & Performance */}
        <div className="md:col-span-8 flex flex-col justify-center space-y-5">
          <div>
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-semibold mb-2">
              <Award className="w-3.5 h-3.5" />
              <span>Chế độ: {mode === 'chapter' ? 'Theo chương' : mode === 'topic' ? 'Theo chủ đề' : 'Tổng hợp'}</span>
            </div>
            <h2 className={`text-2xl font-bold ${perf.color}`}>
              {perf.title}
            </h2>
            <p className="text-sm text-slate-600 mt-1">
              {perf.desc}
            </p>
          </div>

          {/* Stat Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-2xl">
              <div className="flex items-center space-x-2 text-slate-500 text-xs font-medium mb-1">
                <Percent className="w-4 h-4 text-blue-500" />
                <span>Tỷ lệ chính xác</span>
              </div>
              <div className="text-lg font-bold text-slate-800">
                {percentage.toFixed(0)}%
              </div>
            </div>

            <div className="p-3.5 bg-emerald-50/60 border border-emerald-100 rounded-2xl">
              <div className="flex items-center space-x-2 text-emerald-700 text-xs font-medium mb-1">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Số câu đúng</span>
              </div>
              <div className="text-lg font-bold text-emerald-800">
                {correctCount} / {totalQuestions}
              </div>
            </div>

            <div className="p-3.5 bg-slate-50 border border-slate-200/80 rounded-2xl col-span-2 sm:col-span-1">
              <div className="flex items-center space-x-2 text-slate-500 text-xs font-medium mb-1">
                <Clock className="w-4 h-4 text-amber-500" />
                <span>Thời gian làm bài</span>
              </div>
              <div className="text-lg font-bold text-slate-800 truncate">
                {calculateDuration()}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ScoreBoard;
