import React, { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { BookOpen, GraduationCap, Sparkles } from 'lucide-react';
import { checkApiKey, type KeyStatusResponse } from '../api/quiz';

interface LayoutProps {
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const [keyStatus, setKeyStatus] = useState<KeyStatusResponse | null>(null);

  useEffect(() => {
    checkApiKey()
      .then((data) => setKeyStatus(data))
      .catch(() => setKeyStatus(null));
  }, []);

  const isActive = (path: string) => {
    if (path === '/' && location.pathname === '/') return true;
    if (path !== '/' && location.pathname.startsWith(path)) return true;
    return false;
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-slate-800">
      {/* Top Navigation */}
      <header className="sticky top-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200 shadow-xs">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-3 group">
              <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-md shadow-blue-500/20 group-hover:scale-105 transition-transform">
                <GraduationCap className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xl font-extrabold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                  StudyRAG
                </span>
                <span className="hidden sm:inline-block ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-100">
                  AI Quiz & RAG
                </span>
              </div>
            </Link>

            {/* Nav Links & API Key Indicator */}
            <div className="flex items-center space-x-3">
              {keyStatus && (
                <div
                  title={`${keyStatus.provider?.toUpperCase() || 'AI'} (${keyStatus.model || ''}): ${keyStatus.message || ''}`}
                  className={`hidden sm:flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-medium border ${
                    keyStatus.configured && keyStatus.valid
                      ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      : keyStatus.configured
                      ? 'bg-rose-50 text-rose-700 border-rose-200'
                      : 'bg-amber-50 text-amber-700 border-amber-200'
                  }`}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      keyStatus.configured && keyStatus.valid
                        ? 'bg-emerald-500'
                        : keyStatus.configured
                        ? 'bg-rose-500'
                        : 'bg-amber-500 animate-pulse'
                    }`}
                  />
                  <span>
                    {keyStatus.configured && keyStatus.valid
                      ? `${keyStatus.provider === 'openai' ? 'OpenAI' : 'Gemini'}: ${keyStatus.masked_key || 'Sẵn sàng'}`
                      : keyStatus.configured
                      ? `${keyStatus.provider === 'openai' ? 'OpenAI' : 'Gemini'}: Kiểm tra Key`
                      : 'AI API: Chưa có Key'}
                  </span>
                </div>
              )}

              <nav className="flex items-center space-x-1 sm:space-x-3">
                <Link
                  to="/"
                  className={`flex items-center space-x-1.5 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                    isActive('/') && !location.pathname.startsWith('/quiz') && !location.pathname.startsWith('/result')
                      ? 'bg-blue-50 text-blue-700 font-semibold'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  }`}
                >
                  <BookOpen className="w-4 h-4" />
                  <span>Tài liệu</span>
                </Link>
              </nav>
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-200 bg-white py-6 text-center text-xs text-slate-500">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span className="font-semibold text-slate-700">StudyRAG</span>
            <span>— Hệ thống hỗ trợ ôn tập & tạo câu hỏi trắc nghiệm thông minh</span>
          </div>
          <div>
            Powered by RAG & LLM
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
