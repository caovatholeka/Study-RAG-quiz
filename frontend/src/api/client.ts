import axios from 'axios';

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMsg =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'Đã xảy ra lỗi khi kết nối tới máy chủ.';
    console.error('API Error:', errorMsg);
    return Promise.reject(error);
  }
);

export default apiClient;
