import React, { useState } from 'react';
import { ChevronRight, ChevronDown, BookOpen, CheckSquare, Square, MinusSquare } from 'lucide-react';
import type { ChapterItem } from '../types';

interface ChapterTreeProps {
  chapters: ChapterItem[];
  selectedIds: number[];
  onToggleSelect: (id: number) => void;
  onSelectAll?: (ids: number[]) => void;
  onDeselectAll?: () => void;
  onViewChapter?: (chapter: ChapterItem) => void;
}

interface TreeNodeProps {
  chapter: ChapterItem;
  level: number;
  selectedIds: number[];
  onToggleSelect: (id: number) => void;
  onViewChapter?: (chapter: ChapterItem) => void;
}

const TreeNode: React.FC<TreeNodeProps> = ({
  chapter,
  level,
  selectedIds,
  onToggleSelect,
  onViewChapter,
}) => {
  const [isOpen, setIsOpen] = useState<boolean>(true);
  const hasChildren = chapter.children && chapter.children.length > 0;
  const isSelected = selectedIds.includes(chapter.id);

  // Helper to collect all child IDs
  const getAllChildIds = (item: ChapterItem): number[] => {
    let ids: number[] = [item.id];
    if (item.children) {
      item.children.forEach((child) => {
        ids = ids.concat(getAllChildIds(child));
      });
    }
    return ids;
  };

  const childIds = hasChildren ? getAllChildIds(chapter) : [chapter.id];
  const selectedChildCount = childIds.filter((id) => selectedIds.includes(id)).length;
  const isAllChildSelected = selectedChildCount === childIds.length;
  const isPartiallySelected = selectedChildCount > 0 && !isAllChildSelected;

  return (
    <div className="select-none">
      <div
        className={`group flex items-center justify-between py-2 px-2.5 rounded-xl transition-all duration-150 ${
          isSelected
            ? 'bg-blue-50/80 text-blue-900 font-medium'
            : 'hover:bg-slate-100 text-slate-700'
        }`}
        style={{ paddingLeft: `${Math.max(level * 20, 10)}px` }}
      >
        <div className="flex items-center space-x-2.5 min-w-0 flex-1">
          {/* Expand/Collapse toggle */}
          {hasChildren ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsOpen(!isOpen);
              }}
              className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 rounded-md transition-colors"
            >
              {isOpen ? (
                <ChevronDown className="w-4 h-4 text-slate-600" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-600" />
              )}
            </button>
          ) : (
            <div className="w-6 flex items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
            </div>
          )}

          {/* Checkbox */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleSelect(chapter.id);
            }}
            className="text-blue-600 hover:text-blue-700 focus:outline-none transition-colors"
          >
            {isAllChildSelected ? (
              <CheckSquare className="w-4 h-4 text-blue-600" />
            ) : isPartiallySelected ? (
              <MinusSquare className="w-4 h-4 text-blue-500" />
            ) : (
              <Square className="w-4 h-4 text-slate-400 group-hover:text-slate-600" />
            )}
          </button>

          {/* Title */}
          <div
            className="flex-1 min-w-0 cursor-pointer flex items-center space-x-2"
            onClick={() => onToggleSelect(chapter.id)}
          >
            <span className="text-xs font-semibold px-1.5 py-0.5 rounded bg-slate-200/60 text-slate-600">
              #{chapter.chapter_number}
            </span>
            <span className="text-sm truncate" title={chapter.title}>
              {chapter.title}
            </span>
            {chapter.page_start !== null && chapter.page_start !== undefined && (
              <span className="text-[11px] text-slate-400 font-normal">
                (Trang {chapter.page_start}
                {chapter.page_end ? ` - ${chapter.page_end}` : ''})
              </span>
            )}
          </div>
        </div>

        {/* View Chapter details button */}
        {onViewChapter && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onViewChapter(chapter);
            }}
            className="opacity-0 group-hover:opacity-100 flex items-center space-x-1 text-xs text-blue-600 hover:text-blue-800 bg-white hover:bg-blue-50 px-2 py-1 rounded-md border border-slate-200 shadow-xs transition-all"
            title="Xem nội dung chương này"
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>Đọc</span>
          </button>
        )}
      </div>

      {/* Children */}
      {hasChildren && isOpen && (
        <div className="relative border-l border-slate-200 ml-4 pl-1">
          {chapter.children.map((child) => (
            <TreeNode
              key={child.id}
              chapter={child}
              level={level + 1}
              selectedIds={selectedIds}
              onToggleSelect={onToggleSelect}
              onViewChapter={onViewChapter}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const ChapterTree: React.FC<ChapterTreeProps> = ({
  chapters,
  selectedIds,
  onToggleSelect,
  onSelectAll,
  onDeselectAll,
  onViewChapter,
}) => {
  // Collect all IDs
  const collectAllIds = (items: ChapterItem[]): number[] => {
    let ids: number[] = [];
    items.forEach((item) => {
      ids.push(item.id);
      if (item.children && item.children.length > 0) {
        ids = ids.concat(collectAllIds(item.children));
      }
    });
    return ids;
  };

  const allIds = collectAllIds(chapters);

  return (
    <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
      <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100">
        <div>
          <h3 className="text-base font-bold text-slate-800">Cấu trúc chương mục</h3>
          <p className="text-xs text-slate-500">
            Đã chọn {selectedIds.length} / {allIds.length} chương để tạo câu hỏi ôn tập
          </p>
        </div>

        <div className="flex items-center space-x-2">
          {onSelectAll && (
            <button
              type="button"
              onClick={() => onSelectAll(allIds)}
              className="text-xs font-semibold px-2.5 py-1 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            >
              Chọn tất cả
            </button>
          )}
          {onDeselectAll && (
            <button
              type="button"
              onClick={onDeselectAll}
              className="text-xs font-medium px-2.5 py-1 text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
            >
              Bỏ chọn
            </button>
          )}
        </div>
      </div>

      {chapters.length === 0 ? (
        <div className="text-center py-8 text-slate-400 text-sm">
          Tài liệu này chưa có mục lục chương hoặc đang được phân tích.
        </div>
      ) : (
        <div className="space-y-1 max-h-[500px] overflow-y-auto pr-1">
          {chapters.map((chapter) => (
            <TreeNode
              key={chapter.id}
              chapter={chapter}
              level={0}
              selectedIds={selectedIds}
              onToggleSelect={onToggleSelect}
              onViewChapter={onViewChapter}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default ChapterTree;
