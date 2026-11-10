// Type definitions for StudyRAG

export type DocumentStatus = 'processing' | 'ready' | 'error' | string;

export interface DocumentItem {
  id: number;
  user_id?: string | null;
  filename: string;
  original_filename: string;
  file_path?: string;
  status: DocumentStatus;
  file_type: string;
  total_chapters: number;
  created_at: string;
  updated_at?: string;
}

export interface DocumentUploadResponse {
  id: number;
  filename: string;
  original_filename: string;
  status: string;
  file_type: string;
  message: string;
}

export interface DocumentListResponse {
  total: number;
  documents: DocumentItem[];
}

export interface ChapterItem {
  id: number;
  document_id: number;
  chapter_number: number;
  title: string;
  level: string;
  parent_id?: number | null;
  topic_labels?: any;
  page_start?: number | null;
  page_end?: number | null;
  created_at: string;
  children: ChapterItem[];
  content?: string | null;
}

export interface ChapterListResponse {
  document_id: number;
  total_chapters: number;
  chapters: ChapterItem[];
}

export interface ChapterDetailResponse {
  id: number;
  document_id: number;
  chapter_number: number;
  title: string;
  content: string | null;
  level: string;
  parent_id?: number | null;
  topic_labels?: any;
  page_start?: number | null;
  page_end?: number | null;
  created_at: string;
}

export interface ChapterContentResponse {
  chapter_id: number;
  title: string;
  content: string;
  chapter_number: number;
}

export interface QuestionItem {
  id: number;
  question_text: string;
  options: Record<string, string>;
  difficulty: 'easy' | 'medium' | 'hard' | string;
  topic_tag?: string | null;
}

export interface QuizStartRequest {
  chapter_ids?: number[];
  topic_tags?: string[];
  num_questions?: number;
  mode?: 'chapter' | 'topic' | 'full' | string;
}

export interface QuizStartResponse {
  session_id: number;
  total_questions: number;
  mode: string;
  questions: QuestionItem[];
}

export interface QuizAnswerItem {
  question_id: number;
  answer: string;
}

export interface QuizSubmitRequest {
  session_id: number;
  answers: QuizAnswerItem[];
}

export interface DetailedResultItem {
  question_id: number;
  question_text: string;
  options: Record<string, string>;
  user_answer: string;
  correct_answer: string;
  is_correct: boolean;
  explanation?: string | null;
}

export interface QuizResultResponse {
  session_id: number;
  score: number;
  total_questions: number;
  correct_count: number;
  percentage: number;
  mode: string;
  started_at: string;
  finished_at: string;
  results: DetailedResultItem[];
}

export interface QuizSessionSummary {
  id: number;
  user_id?: string | null;
  document_id: number;
  chapter_ids: number[];
  mode: string;
  score?: number | null;
  total_questions: number;
  started_at: string;
  finished_at?: string | null;
}

export interface QuizSessionListResponse {
  total: number;
  sessions: QuizSessionSummary[];
}

export interface GenerateQuizResponse {
  message: string;
  document_id: number;
  existing_questions: number;
}
