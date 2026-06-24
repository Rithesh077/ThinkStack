/**
 * api client for the thinkstack backend.
 *
 * all paper writer endpoints live under /api/papers.
 */

const BASE_URL = "/api";

async function request(path: string, options: RequestInit = {}) {
  const url = `${BASE_URL}${path}`;
  const config: RequestInit = {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  };

  if (
    config.body &&
    typeof config.body === "object" &&
    !(config.body instanceof FormData)
  ) {
    config.body = JSON.stringify(config.body);
  }

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `request failed: ${response.status}`);
  }

  return response.json();
}

export const papersApi = {
  createProject: (name: string) =>
    request("/papers/projects", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  listProjects: () => request("/papers/projects"),

  getProject: (projectId: string) =>
    request(`/papers/projects/${projectId}`),

  saveSource: (projectId: string, source: string) =>
    request("/papers/save", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, source }),
    }),

  generateLatex: (projectId: string, prompt: string, currentSource: string = "") =>
    request("/papers/generate", {
      method: "POST",
      body: JSON.stringify({
        project_id: projectId,
        prompt,
        current_source: currentSource,
      }),
    }),

  compile: (projectId: string) =>
    request("/papers/compile", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId }),
    }),

  downloadUrl: (projectId: string) => `/api/papers/download/${projectId}`,

  deleteProject: (projectId: string) =>
    request(`/papers/projects/${projectId}`, { method: "DELETE" }),
};
