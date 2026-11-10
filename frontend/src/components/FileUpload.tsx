import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertCircle, X } from 'lucide-react';
import { uploadDocument } from '../api/documents';
import type { DocumentUploadResponse } from '../types';

interface FileUploadProps {
  onUploadSuccess?: (doc: DocumentUploadResponse) => void;
}

export const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess }) => {
  const [dragActive, setDragActive] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const allowedTypes = ['.pdf', '.docx', '.doc', '.txt'];

  const validateFile = (file: File): boolean => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedTypes.includes(ext)) {
      setErrorMsg(`Định dạng file không hỗ trợ (${ext}). Chỉ chấp nhận: PDF, DOCX, DOC, TXT.`);
      return false;
    }
    // Limit to 50MB
    if (file.size > 50 * 1024 * 1024) {
      setErrorMsg('Dung lượng file tối đa là 50MB.');
      return false;
    }
    return true;
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
        setErrorMsg(null);
        setSuccessMsg(null);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (validateFile(file)) {
        setSelectedFile(file);
        setErrorMsg(null);
        setSuccessMsg(null);
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setProgress(0);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await uploadDocument(selectedFile, (percent) => {
        setProgress(percent);
      });
      setSuccessMsg(`Tải lên thành công! Tài liệu đang được xử lý.`);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      if (onUploadSuccess) {
        onUploadSuccess(res);
      }
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Tải lên thất bại. Vui lòng kiểm tra lại kết nối.';
      setErrorMsg(typeof msg === 'string' ? msg : JSON.stringify(msg));
    } finally {
      setIsUploading(false);
    }
  };

  const handleClear = () => {
    setSelectedFile(null);
    setProgress(0);
    setErrorMsg(null);
    setSuccessMsg(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    else if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    else return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  return (
    <div className="w-full bg-white rounded-2xl border border-slate-200 shadow-sm p-6 transition-all hover:shadow-md">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-bold text-slate-800">Tải lên tài liệu học tập</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Hỗ trợ tài liệu giáo trình, slide bài giảng định dạng PDF, DOCX, DOC hoặc TXT
          </p>
        </div>
        <div className="text-xs font-semibold px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-100">
          Max 50MB
        </div>
      </div>

      <div
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
          dragActive
            ? 'border-blue-500 bg-blue-50/60 scale-[1.01]'
            : selectedFile
            ? 'border-blue-300 bg-blue-50/20'
            : 'border-slate-300 hover:border-blue-400 bg-slate-50/50 hover:bg-slate-50'
        }`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.doc,.txt"
          className="hidden"
          onChange={handleFileChange}
          disabled={isUploading}
        />

        <div className="flex flex-col items-center justify-center space-y-3 pointer-events-none">
          <div className="w-14 h-14 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 shadow-sm">
            <UploadCloud className="w-7 h-7" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-700">
              Kéo và thả tài liệu vào đây hoặc <span className="text-blue-600 underline">chọn file</span> từ máy tính
            </p>
            <p className="text-xs text-slate-400 mt-1">
              Định dạng hỗ trợ: PDF, DOCX, DOC, TXT (tối đa 50MB)
            </p>
          </div>
        </div>
      </div>

      {/* Selected File Card */}
      {selectedFile && (
        <div className="mt-4 p-4 bg-slate-50 border border-slate-200 rounded-xl flex items-center justify-between">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="p-2.5 bg-blue-100 text-blue-600 rounded-lg">
              <FileText className="w-5 h-5" />
            </div>
            <div className="truncate">
              <p className="text-sm font-medium text-slate-800 truncate">
                {selectedFile.name}
              </p>
              <p className="text-xs text-slate-500">
                {formatFileSize(selectedFile.size)}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2 flex-shrink-0">
            {!isUploading && (
              <button
                type="button"
                onClick={handleClear}
                className="p-1.5 text-slate-400 hover:text-rose-500 rounded-lg hover:bg-white transition-colors"
                title="Bỏ chọn file"
              >
                <X className="w-5 h-5" />
              </button>
            )}
            <button
              type="button"
              disabled={isUploading}
              onClick={handleUpload}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-medium text-xs rounded-lg shadow-sm transition-all hover:shadow"
            >
              {isUploading ? 'Đang tải lên...' : 'Tải lên ngay'}
            </button>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      {isUploading && (
        <div className="mt-4 space-y-1.5 animate-fade-in">
          <div className="flex justify-between text-xs font-semibold text-slate-600">
            <span>Tiến trình tải lên</span>
            <span>{progress}%</span>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-300 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Success Notification */}
      {successMsg && (
        <div className="mt-4 p-3.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-center space-x-2 animate-fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span className="font-medium">{successMsg}</span>
        </div>
      )}

      {/* Error Notification */}
      {errorMsg && (
        <div className="mt-4 p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center space-x-2 animate-fade-in">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span className="font-medium">{errorMsg}</span>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
