import apiClient from './client';
import type {
  ChapterListResponse,
  ChapterDetailResponse,
  ChapterContentResponse,
} from '../types';

export const getChapters = async (
  documentId: number | string
): Promise<ChapterListResponse> => {
  const response = await apiClient.get<ChapterListResponse>(
    `/chapters/document/${documentId}`
  );
  return response.data;
};

export const getChapter = async (
  chapterId: number | string
): Promise<ChapterDetailResponse> => {
  const response = await apiClient.get<ChapterDetailResponse>(
    `/chapters/${chapterId}`
  );
  return response.data;
};

export const getChapterContent = async (
  chapterId: number | string
): Promise<ChapterContentResponse> => {
  const response = await apiClient.get<ChapterContentResponse>(
    `/chapters/${chapterId}/content`
  );
  return response.data;
};
