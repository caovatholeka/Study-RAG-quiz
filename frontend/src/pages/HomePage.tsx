import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  Trash2,
  ChevronRight,
  BookOpen,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { getDocuments, deleteDocument } from '../api/documents';
import type { DocumentItem, DocumentUploadResponse } from '../types';
import FileUpload from '../components/FileUpload';
import LoadingSpinner from '../components/LoadingSpinner';

export const HomePage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const navigate = useNavigate();
  const pollingRef = useRef<any>(null);

  const fetchDocuments = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const data = await getDocuments();
      setDocuments(data.documents);
      setErrorMessage(null);
    } catch (err: any) {
      console.error(err);
      if (!isSilent) {
        setErrorMessage('Không thể tải danh sách tài liệu. Hãy chắc chắn backend đang chạy tại port 8000.');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Auto-poll if any document is in 'processing' status
  useEffect(() => {
    const hasProcessing = documents.some((doc) => doc.status === 'processing');

    if (hasProcessing) {
      pollingRef.current = setInterval(() => {
        fetchDocuments(true);
      }, 3000);
    } else {
      if (pollingRef.current) clearInterval(pollingRef.current);
    }

    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [documents, fetchDocuments]);

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    if (!window.confirm('Bạn có chắc chắn muốn xóa tài liệu này cùng toàn bộ câu hỏi liên quan?')) {
      return;
    }

    setDeleteId(id);
    try {
      await deleteDocument(id);
      setDocuments((prev) => prev.filter((doc) => doc.id !== id));
    } catch (err: any) {
      alert('Không thể xóa tài liệu. Vui lòng thử lại sau.');
    } finally {
      setDeleteId(null);
    }
  };

  const handleUploadSuccess = (_newDoc: DocumentUploadResponse) => {
    fetchDocuments(true);
  };

  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'ready':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Sẵn sàng</span>
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 animate-pulse">
            <Clock className="w-3.5 h-3.5 animate-spin" />
            <span>Đang xử lý...</span>
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Lỗi</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
            {status}
          </span>
        );
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('vi-VN', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero Header */}
      <div className="bg-gradient-to-r from-blue-600 via-blue-700 to-indigo-700 rounded-3xl p-6 sm:p-10 text-white shadow-lg relative overflow-hidden">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-white/20 backdrop-blur-md rounded-full text-xs font-semibold mb-3">
            <Sparkles className="w-3.5 h-3.5" />
            <span>StudyRAG Assistant</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Ôn tập thông minh cùng Trợ lý Học tập AI
          </h1>
          <p className="mt-2 text-sm sm:text-base text-blue-100 leading-relaxed">
            Tải lên tài liệu PDF, DOCX của bạn để tự động phân tích cấu trúc chương mục, tạo ngân hàng câu hỏi trắc nghiệm và ôn tập theo từng chủ đề.
          </p>
        </div>
      </div>

      {/* Upload Zone */}
      <section>
        <FileUpload onUploadSuccess={handleUploadSuccess} />
      </section>

      {/* Document List Section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-slate-800">Kho tài liệu của bạn</h2>
            <p className="text-xs text-slate-500">
              Tổng cộng {documents.length} tài liệu đã tải lên
            </p>
          </div>

          <button
            type="button"
            onClick={() => fetchDocuments()}
            disabled={refreshing}
            className="flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 hover:bg-slate-100 rounded-xl transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span>Làm mới</span>
          </button>
        </div>

        {errorMessage && (
          <div className="p-4 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-sm flex items-center space-x-2">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {loading ? (
          <LoadingSpinner message="Đang tải danh sách tài liệu..." />
        ) : documents.length === 0 ? (
          <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-xs">
            <div className="w-16 h-16 rounded-full bg-blue-50 text-blue-500 mx-auto flex items-center justify-center mb-4">
              <BookOpen className="w-8 h-8" />
            </div>
            <h3 className="text-base font-bold text-slate-800">Chưa có tài liệu nào</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto">
              Hãy kéo thả tài liệu giáo trình hoặc bài giảng ở phía trên để bắt đầu học tập và làm trắc nghiệm!
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {documents.map((doc) => (
              <div
                key={doc.id}
                onClick={() => navigate(`/document/${doc.id}`)}
                className="group relative bg-white rounded-2xl border border-slate-200 p-5 shadow-xs hover:shadow-md hover:border-blue-400 cursor-pointer transition-all flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center space-x-3 min-w-0">
                      <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 group-hover:bg-blue-600 group-hover:text-white transition-colors">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div className="min-w-0">
                        <h4
                          className="text-sm font-bold text-slate-800 truncate group-hover:text-blue-600 transition-colors"
                          title={doc.original_filename}
                        >
                          {doc.original_filename}
                        </h4>
                        <span className="text-[11px] font-semibold text-slate-400 uppercase">
                          {doc.file_type}
                        </span>
                      </div>
                    </div>

                    <div className="flex-shrink-0">
                      {renderStatusBadge(doc.status)}
                    </div>
                  </div>

                  <div className="flex items-center space-x-4 text-xs text-slate-500 mt-2">
                    <span className="flex items-center space-x-1">
                      <BookOpen className="w-3.5 h-3.5 text-slate-400" />
                      <span>{doc.total_chapters || 0} chương/mục</span>
                    </span>
                    <span>•</span>
                    <span>{formatDate(doc.created_at)}</span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs font-semibold text-blue-600 flex items-center space-x-1 group-hover:translate-x-0.5 transition-transform">
                    <span>Xem chi tiết & Ôn tập</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </span>

                  <button
                    type="button"
                    disabled={deleteId === doc.id}
                    onClick={(e) => handleDelete(e, doc.id)}
                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors"
                    title="Xóa tài liệu"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
};

export default HomePage;
