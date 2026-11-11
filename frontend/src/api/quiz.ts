import apiClient from './client';
import type {
  QuizStartRequest,
  QuizStartResponse,
  QuizSubmitRequest,
  QuizResultResponse,
  QuizSessionListResponse,
  GenerateQuizResponse,
} from '../types';

export const startQuiz = async (
  request: QuizStartRequest
): Promise<QuizStartResponse> => {
  const response = await apiClient.post<QuizStartResponse>('/quiz/start', request);
  return response.data;
};

export const submitQuiz = async (
  request: QuizSubmitRequest
): Promise<QuizResultResponse> => {
  const response = await apiClient.post<QuizResultResponse>('/quiz/submit', request);
  return response.data;
};

export const getSessions = async (): Promise<QuizSessionListResponse> => {
  const response = await apiClient.get<QuizSessionListResponse>('/quiz/sessions');
  return response.data;
};

export const getSession = async (
  sessionId: number | string
): Promise<QuizResultResponse> => {
  const response = await apiClient.get<QuizResultResponse>(
    `/quiz/sessions/${sessionId}`
  );
  return response.data;
};

export interface QuizStatsResponse {
  document_id: number;
  total_questions: number;
  verified_questions: number;
  is_generating: boolean;
  progress_message: string;
  error?: string | null;
}

export const getQuizStats = async (
  documentId: number | string
): Promise<QuizStatsResponse> => {
  const response = await apiClient.get<QuizStatsResponse>(
    `/quiz/stats/${documentId}`
  );
  return response.data;
};

export const generateQuiz = async (
  documentId: number | string,
  numQuestions?: number
): Promise<GenerateQuizResponse> => {
  const url = numQuestions
    ? `/quiz/generate/${documentId}?num_questions=${numQuestions}`
    : `/quiz/generate/${documentId}`;
  const response = await apiClient.post<GenerateQuizResponse>(url);
  return response.data;
};

export interface KeyStatusResponse {
  configured: boolean;
  valid?: boolean;
  provider?: string;
  masked_key?: string | null;
  model?: string;
  message?: string;
}

export const checkApiKey = async (): Promise<KeyStatusResponse> => {
  const response = await apiClient.get<KeyStatusResponse>('/quiz/check-key');
  return response.data;
};
