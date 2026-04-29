import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Pipeline API ─────────────────────────────────────────────
export const triggerPipeline = () =>
  api.post('/api/v1/pipeline/run');

export const getPipelineRuns = () =>
  api.get('/api/v1/pipeline/runs');

export const getPipelineRun = (runId: string) =>
  api.get(`/api/v1/pipeline/runs/${runId}`);

// ── Reconciliation API ───────────────────────────────────────
export interface ReconciliationFilters {
  period?: string;
  priority?: string;
  type?: string;
  needs_review?: boolean;
  resolved?: boolean;
  page?: number;
  limit?: number;
}

export const getReconciliation = (filters: ReconciliationFilters = {}) =>
  api.get('/api/v1/reconciliation', { params: filters });

export const getReconciliationDetail = (id: string) =>
  api.get(`/api/v1/reconciliation/${id}`);

export const resolveReconciliation = (id: string, data: { resolved_by: string; resolution_notes: string }) =>
  api.patch(`/api/v1/reconciliation/${id}/resolve`, data);

// ── Workers API ──────────────────────────────────────────────
export const getWorkers = (params: { search?: string; page?: number; limit?: number } = {}) =>
  api.get('/api/v1/workers', { params });

export const getWorker = (workerId: string) =>
  api.get(`/api/v1/workers/${workerId}`);

export const getWorkerAuditTrail = (workerId: string) =>
  api.get(`/api/v1/workers/${workerId}/audit-trail`);

// ── Stats API ────────────────────────────────────────────────
export const getDashboardStats = (period?: string) =>
  api.get('/api/v1/stats/summary', { params: period ? { period } : {} });

// ── Health Check ─────────────────────────────────────────────
export const healthCheck = () =>
  api.get('/api/v1/health');

export default api;
