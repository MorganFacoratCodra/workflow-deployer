import type { Execution, NodeRun, Workflow, WorkflowGraph } from '../types'

const API_URL = (import.meta.env.VITE_API_URL || '/api').replace(/\/$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!response.ok) {
    const body = await response.text()
    throw new Error(body || `Request failed: ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

export const api = {
  listWorkflows: () => request<Workflow[]>('/workflows'),
  getWorkflow: (id: number) => request<Workflow>(`/workflows/${id}`),
  createWorkflow: (payload: { name: string; version: number; graph: WorkflowGraph }) =>
    request<Workflow>('/workflows', { method: 'POST', body: JSON.stringify(payload) }),
  updateWorkflow: (id: number, payload: { name: string; version: number; graph: WorkflowGraph }) =>
    request<Workflow>(`/workflows/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteWorkflow: (id: number) => request<void>(`/workflows/${id}`, { method: 'DELETE' }),
  exportWorkflow: (id: number) => request<Workflow>(`/workflows/${id}/export`),
  importWorkflow: (payload: { name: string; version: number; graph: WorkflowGraph }) =>
    request<Workflow>('/workflows/import', { method: 'POST', body: JSON.stringify(payload) }),
  runWorkflow: (id: number) => request<{ execution_id: number }>(`/workflows/${id}/run`, { method: 'POST' }),
  listExecutions: () => request<(Execution & { node_runs: NodeRun[] })[]>('/executions'),
  getExecution: (id: number) => request<Execution & { node_runs: NodeRun[] }>(`/executions/${id}`),
}
