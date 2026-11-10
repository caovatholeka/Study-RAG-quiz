import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import DocumentPage from './pages/DocumentPage';
import ChapterPage from './pages/ChapterPage';
import QuizPage from './pages/QuizPage';
import ResultPage from './pages/ResultPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/document/:id" element={<DocumentPage />} />
          <Route path="/chapter/:id" element={<ChapterPage />} />
          <Route path="/quiz/:sessionId" element={<QuizPage />} />
          <Route path="/result/:sessionId" element={<ResultPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
};

export default App;
