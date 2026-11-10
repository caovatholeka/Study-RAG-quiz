import apiClient from './client';
import type {
  DocumentUploadResponse,
  DocumentListResponse,
  DocumentItem,
} from '../types';

export const uploadDocument = async (
  file: File,
  onProgress?: (percent: number) => void
): Promise<DocumentUploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<DocumentUploadResponse>(
    '/documents/upload',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percent);
        }
      },
    }
  );
  return response.data;
};

export const getDocuments = async (): Promise<DocumentListResponse> => {
  const response = await apiClient.get<DocumentListResponse>('/documents/');
  return response.data;
};

export const getDocument = async (id: number | string): Promise<DocumentItem> => {
  const response = await apiClient.get<DocumentItem>(`/documents/${id}`);
  return response.data;
};

export const deleteDocument = async (
  id: number | string
): Promise<{ message: string; document_id: number }> => {
  const response = await apiClient.delete<{ message: string; document_id: number }>(
    `/documents/${id}`
  );
  return response.data;
};
