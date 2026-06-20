/**
 * api client utility for scholarlens backend.
 *
 * provides typed fetch wrappers for all backend endpoints
 * with consistent error handling and response parsing.
 */

const BASE_URL = '/api';

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  };

  if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
    config.body = JSON.stringify(config.body);
  }

  if (config.body instanceof FormData) {
    delete config.headers['Content-Type'];
  }

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `request failed: ${response.status}`);
  }

  return response.json();
}

export const documentsApi = {
  upload: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return request('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },

  list: () => request('/documents'),

  get: (docId) => request(`/documents/${docId}`),

  delete: (docId) => request(`/documents/${docId}`, { method: 'DELETE' }),
};

export const searchApi = {
  search: (query, topK = 10, docIds = []) =>
    request('/search', {
      method: 'POST',
      body: { query, top_k: topK, doc_ids: docIds },
    }),
};

export const analysisApi = {
  summarize: (docIds) =>
    request('/analysis/summarize', {
      method: 'POST',
      body: { doc_ids: docIds },
    }),

  extractClaims: (docIds) =>
    request('/analysis/claims', {
      method: 'POST',
      body: { doc_ids: docIds },
    }),

  clusterThemes: (docIds) =>
    request('/analysis/themes', {
      method: 'POST',
      body: { doc_ids: docIds },
    }),
};

export const gapsApi = {
  analyze: (docIds) =>
    request('/gaps/analyze', {
      method: 'POST',
      body: { doc_ids: docIds },
    }),
};

export const systemApi = {
  health: () => request('/system/health'),
  models: () => request('/system/models'),
  stats: () => request('/system/stats'),
};
