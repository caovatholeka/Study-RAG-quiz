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

export const generateQuiz = async (
  documentId: number | string
): Promise<GenerateQuizResponse> => {
  const response = await apiClient.post<GenerateQuizResponse>(
    `/quiz/generate/${documentId}`
  );
  return response.data;
};
