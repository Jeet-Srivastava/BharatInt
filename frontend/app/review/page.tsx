'use client';

import { Suspense, useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'next/navigation';
import { getReconciliation, getReconciliationDetail, resolveReconciliation } from '@/lib/api';
import { formatPaise, formatDelta, formatPeriod, getPriorityBadge, getTypeBadge, formatConfidence } from '@/lib/formatters';

function parseBooleanFilter(value: string | null): boolean | undefined {
  if (value === 'true') return true;
  if (value === 'false') return false;
  return undefined;
}

type ReviewFiltersState = {
  period: string;
  priority: string;
  type: string;
  needs_review: boolean | undefined;
  resolved: boolean | undefined;
};

function ReviewQueueContent() {
  const searchParams = useSearchParams();
  const [records, setRecords] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ReviewFiltersState>(() => ({
    period: searchParams.get('period') || '',
    priority: searchParams.get('priority') || '',
    type: searchParams.get('type') || '',
    needs_review: parseBooleanFilter(searchParams.get('needs_review')) ?? true,
    resolved: parseBooleanFilter(searchParams.get('resolved')) ?? false,
  }));
  const [selectedRecord, setSelectedRecord] = useState<any>(null);
  const [drawerLoading, setDrawerLoading] = useState(false);
  const [resolveNotes, setResolveNotes] = useState('');
  const [resolveBy, setResolveBy] = useState('');
  const [resolving, setResolving] = useState(false);

  const fetchRecords = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, limit: 50 };
      if (filters.period) params.period = filters.period;
      if (filters.priority) params.priority = filters.priority;
      if (filters.type) params.type = filters.type;
      if (filters.needs_review !== undefined) params.needs_review = filters.needs_review;
      if (filters.resolved !== undefined) params.resolved = filters.resolved;
      const res = await getReconciliation(params);
      setRecords(res.data.records);
      setTotal(res.data.total);
    } catch {
      setRecords([]);
    } finally {
      setLoading(false);
    }
  }, [page, filters]);

  useEffect(() => {
    fetchRecords();
  }, [fetchRecords]);

  const openDrawerById = useCallback(async (recordId: string) => {
    setDrawerLoading(true);
    setSelectedRecord(null);
    try {
      const res = await getReconciliationDetail(recordId);
      setSelectedRecord(res.data);
    } catch {
      setSelectedRecord(null);
    }
    setDrawerLoading(false);
  }, []);

  const openDrawer = async (record: any) => {
    await openDrawerById(record.id);
  };

  useEffect(() => {
    const period = searchParams.get('period') || '';
    const priority = searchParams.get('priority') || '';
    const type = searchParams.get('type') || '';
    const needsReview = parseBooleanFilter(searchParams.get('needs_review'));
    const resolved = parseBooleanFilter(searchParams.get('resolved'));

    setFilters((current) => {
      const next = {
        period,
        priority,
        type,
        needs_review: needsReview ?? true,
        resolved: resolved ?? false,
      };

      const unchanged =
        current.period === next.period &&
        current.priority === next.priority &&
        current.type === next.type &&
        current.needs_review === next.needs_review &&
        current.resolved === next.resolved;

      return unchanged ? current : next;
    });
    setPage(1);
  }, [searchParams]);

  useEffect(() => {
    const recordId = searchParams.get('recordId');
    if (!recordId) return;
    openDrawerById(recordId);
  }, [openDrawerById, searchParams]);

  const handleResolve = async () => {
    if (!selectedRecord || !resolveBy) return;
    setResolving(true);
    try {
      await resolveReconciliation(selectedRecord.id, {
        resolved_by: resolveBy,
        resolution_notes: resolveNotes,
      });
      setSelectedRecord(null);
      setResolveNotes('');
      setResolveBy('');
      fetchRecords();
    } catch (err) {
      console.error('Failed to resolve:', err);
    }
    setResolving(false);
  };

  const totalPages = Math.ceil(total / 50);

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Review Queue</h1>
          <p className="text-sm text-slate-500 mt-1">{total} records matching filters</p>
        </div>
      </div>

      {/* Filters */}
      <div className="glass-card p-4 flex flex-wrap gap-3 items-center">
        <select
          className="select-field"
          value={filters.period}
          onChange={(e) => {
            setPage(1);
            setFilters({ ...filters, period: e.target.value });
          }}
        >
          <option value="">All Periods</option>
          <option value="2025-01">Jan 2025</option>
          <option value="2025-02">Feb 2025</option>
          <option value="2025-03">Mar 2025</option>
        </select>

        <select
          className="select-field"
          value={filters.priority}
          onChange={(e) => {
            setPage(1);
            setFilters({ ...filters, priority: e.target.value });
          }}
        >
          <option value="">All Priorities</option>
          <option value="P0">P0 Critical</option>
          <option value="P1">P1 High</option>
          <option value="P2">P2 Medium</option>
          <option value="P3">P3 Low</option>
        </select>

        <select
          className="select-field"
          value={filters.type}
          onChange={(e) => {
            setPage(1);
            setFilters({ ...filters, type: e.target.value });
          }}
        >
          <option value="">All Types</option>
          <option value="UNDERPAYMENT">Underpayment</option>
          <option value="OVERPAYMENT">Overpayment</option>
          <option value="UNMATCHED_WORK">Unmatched Work</option>
          <option value="UNMATCHED_PAYMENT">Unmatched Payment</option>
          <option value="DUPLICATE_PAYMENT">Duplicate Payment</option>
          <option value="NEAR_MATCH">Near Match</option>
          <option value="EXACT_MATCH">Exact Match</option>
        </select>

        <select
          className="select-field"
          value={filters.resolved === undefined ? '' : filters.resolved ? 'true' : 'false'}
          onChange={(e) => {
            const val = e.target.value;
            setPage(1);
            setFilters({ ...filters, resolved: val === '' ? undefined : val === 'true' });
          }}
        >
          <option value="">All Status</option>
          <option value="false">Unresolved</option>
          <option value="true">Resolved</option>
        </select>

        <button
          className="btn btn-ghost text-xs"
          onClick={() => {
            setPage(1);
            setFilters({ period: '', priority: '', type: '', needs_review: undefined, resolved: undefined });
          }}
        >
          Clear Filters
        </button>
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Worker</th>
                <th>Period</th>
                <th>Expected</th>
                <th>Actual</th>
                <th>Delta</th>
                <th>Type</th>
                <th>Priority</th>
                <th>Reason</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 9 }).map((_, j) => (
                      <td key={j}><div className="h-4 w-20 shimmer rounded" /></td>
                    ))}
                  </tr>
                ))
              ) : records.length === 0 ? (
                <tr>
                  <td colSpan={9} className="text-center py-12 text-slate-500">
                    No records found. Adjust filters or run the pipeline.
                  </td>
                </tr>
              ) : (
                records.map((r) => {
                  const d = formatDelta(r.delta_paise);
                  const priority = getPriorityBadge(r.priority);
                  const type = getTypeBadge(r.discrepancy_type);
                  return (
                    <tr
                      key={r.id}
                      className="cursor-pointer"
                      onClick={() => openDrawer(r)}
                    >
                      <td>
                        <div>
                          <span className="text-white font-medium text-xs">{r.worker_name || r.worker_id}</span>
                          <span className="block text-[10px] text-slate-500">{r.worker_id}</span>
                        </div>
                      </td>
                      <td className="text-xs">{formatPeriod(r.billing_period)}</td>
                      <td className="text-xs font-mono">{formatPaise(r.expected_paise)}</td>
                      <td className="text-xs font-mono">{formatPaise(r.actual_paise)}</td>
                      <td className={`text-xs font-mono font-semibold ${d.color}`}>{d.text}</td>
                      <td><span className={`badge ${type.classes}`}>{type.text}</span></td>
                      <td><span className={`badge ${priority.classes}`}>{priority.text}</span></td>
                      <td className="max-w-[200px]">
                        <span className="text-[11px] text-slate-500 line-clamp-2">{r.review_reason || '—'}</span>
                      </td>
                      <td>
                        {r.resolved ? (
                          <span className="badge bg-emerald-500/20 text-emerald-400">Resolved</span>
                        ) : (
                          <span className="badge bg-amber-500/20 text-amber-400">Pending</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between p-4 border-t border-[#1E293B]">
            <span className="text-xs text-slate-500">
              Page {page} of {totalPages} · {total} total records
            </span>
            <div className="flex gap-2">
              <button
                className="btn btn-ghost text-xs py-1.5 px-3"
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
              >
                Previous
              </button>
              <button
                className="btn btn-ghost text-xs py-1.5 px-3"
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Detail Drawer */}
      {(selectedRecord || drawerLoading) && (
        <>
          <div className="drawer-overlay" onClick={() => setSelectedRecord(null)} />
          <div className="drawer-panel p-6">
            {drawerLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={i} className="h-6 shimmer rounded" />
                ))}
              </div>
            ) : selectedRecord && (
              <div className="space-y-6">
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-lg font-bold text-white">{selectedRecord.worker_name || selectedRecord.worker_id}</h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {selectedRecord.worker_id} · {selectedRecord.worker_phone} · {formatPeriod(selectedRecord.billing_period)}
                    </p>
                  </div>
                  <button
                    className="text-slate-500 hover:text-white transition-colors"
                    onClick={() => setSelectedRecord(null)}
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Summary */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-[#0B1121] rounded-xl p-3">
                    <p className="text-[10px] text-slate-500 uppercase">Expected</p>
                    <p className="text-sm font-bold text-blue-400 font-mono">{formatPaise(selectedRecord.expected_paise)}</p>
                  </div>
                  <div className="bg-[#0B1121] rounded-xl p-3">
                    <p className="text-[10px] text-slate-500 uppercase">Actual</p>
                    <p className="text-sm font-bold text-emerald-400 font-mono">{formatPaise(selectedRecord.actual_paise)}</p>
                  </div>
                  <div className="bg-[#0B1121] rounded-xl p-3">
                    <p className="text-[10px] text-slate-500 uppercase">Delta</p>
                    <p className={`text-sm font-bold font-mono ${formatDelta(selectedRecord.delta_paise).color}`}>
                      {formatDelta(selectedRecord.delta_paise).text}
                    </p>
                  </div>
                </div>

                {/* Badges */}
                <div className="flex flex-wrap gap-2">
                  <span className={`badge ${getTypeBadge(selectedRecord.discrepancy_type).classes}`}>
                    {getTypeBadge(selectedRecord.discrepancy_type).text}
                  </span>
                  <span className={`badge ${getPriorityBadge(selectedRecord.priority).classes}`}>
                    {getPriorityBadge(selectedRecord.priority).text}
                  </span>
                  <span className={`badge ${formatConfidence(selectedRecord.confidence_score).color} bg-white/5`}>
                    Confidence: {formatConfidence(selectedRecord.confidence_score).text}
                  </span>
                </div>

                {/* Review Reasons */}
                {selectedRecord.review_reason && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Review Reasons</h4>
                    <div className="space-y-1.5">
                      {selectedRecord.review_reason.split(' | ').map((reason: string, idx: number) => (
                        <div key={idx} className="flex items-start gap-2 text-xs">
                          <span className="text-amber-400 mt-0.5">⚠</span>
                          <span className="text-slate-300">{reason}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Confidence Breakdown */}
                {selectedRecord.confidence_breakdown && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Confidence Breakdown</h4>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="bg-[#0B1121] rounded-lg p-3">
                        <p className="text-slate-500">Identity</p>
                        <p className="text-white font-semibold mt-1">
                          {formatConfidence(selectedRecord.confidence_breakdown.identity_score).text}
                        </p>
                        <p className="text-slate-500 mt-1">Weight 40%</p>
                      </div>
                      <div className="bg-[#0B1121] rounded-lg p-3">
                        <p className="text-slate-500">Rate Resolution</p>
                        <p className="text-white font-semibold mt-1">{selectedRecord.confidence_breakdown.rate_status}</p>
                        <p className="text-slate-500 mt-1">Weight 30%</p>
                      </div>
                      <div className="bg-[#0B1121] rounded-lg p-3">
                        <p className="text-slate-500">Timezone</p>
                        <p className="text-white font-semibold mt-1">
                          {selectedRecord.confidence_breakdown.tz_corrected ? 'Corrected' : 'Clean'}
                        </p>
                        <p className="text-slate-500 mt-1">Weight 20%</p>
                      </div>
                      <div className="bg-[#0B1121] rounded-lg p-3">
                        <p className="text-slate-500">Hours</p>
                        <p className="text-white font-semibold mt-1">
                          {selectedRecord.confidence_breakdown.hours_anomaly ? 'Anomaly Flagged' : 'Clean'}
                        </p>
                        <p className="text-slate-500 mt-1">Weight 10%</p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Shifts */}
                {selectedRecord.shifts?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Shifts ({selectedRecord.shifts.length})</h4>
                    <div className="space-y-1.5">
                      {selectedRecord.shifts.map((s: any) => (
                        <div key={s.log_id} className="bg-[#0B1121] rounded-lg p-3 text-xs">
                          <div className="flex justify-between gap-3">
                            <div>
                              <span className="text-white font-medium">{s.log_id}</span>
                              <div className="flex gap-4 mt-1 text-slate-500">
                                <span>{s.hours}h</span>
                                <span>{s.vendor_app}</span>
                                <span>Supervisor: {s.supervisor_id}</span>
                              </div>
                            </div>
                            <div className="text-right">
                              <span className="text-slate-400">{s.work_date}</span>
                              <div className="mt-1 space-y-1">
                                <p className="text-blue-400 font-mono">{s.rate_paise ? formatPaise(s.rate_paise) : s.rate_status}</p>
                                <p className="text-emerald-400 font-mono">{s.expected_paise ? formatPaise(s.expected_paise) : 'No expected wage'}</p>
                              </div>
                            </div>
                          </div>
                          <div className="flex gap-4 mt-2 text-slate-500">
                            <span>Identity: {formatConfidence(s.identity_confidence).text}</span>
                            {s.tz_corrected && <span className="text-amber-400">TZ Corrected</span>}
                            {s.hours_anomaly && <span className="text-red-400">Anomaly</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Transfers */}
                {selectedRecord.transfers?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-semibold text-slate-400 uppercase mb-2">Transfers ({selectedRecord.transfers.length})</h4>
                    <div className="space-y-1.5">
                      {selectedRecord.transfers.map((t: any) => (
                        <div key={t.utr} className="bg-[#0B1121] rounded-lg p-3 text-xs">
                          <div className="flex justify-between">
                            <span className="text-white font-medium font-mono">{t.utr}</span>
                            <span className="text-emerald-400 font-mono">{formatPaise(t.amount_paise)}</span>
                          </div>
                          <div className="flex gap-4 mt-1 text-slate-500">
                            <span>{t.transfer_date}</span>
                            <span>Acc: ****{t.account_last4}</span>
                            {t.precision_bug && <span className="text-amber-400">Precision Bug</span>}
                            {t.low_value && <span className="text-red-400">Low Value</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Resolve Form */}
                {!selectedRecord.resolved && (
                  <div className="border-t border-[#1E293B] pt-5">
                    <h4 className="text-xs font-semibold text-slate-400 uppercase mb-3">Mark as Resolved</h4>
                    <div className="space-y-3">
                      <input
                        type="text"
                        placeholder="Resolved by (your name)"
                        className="input-field"
                        value={resolveBy}
                        onChange={(e) => setResolveBy(e.target.value)}
                      />
                      <textarea
                        placeholder="Resolution notes..."
                        className="input-field min-h-[80px] resize-y"
                        value={resolveNotes}
                        onChange={(e) => setResolveNotes(e.target.value)}
                      />
                      <button
                        className="btn btn-primary w-full"
                        onClick={handleResolve}
                        disabled={!resolveBy || resolving}
                      >
                        {resolving ? 'Resolving...' : 'Mark Resolved'}
                      </button>
                    </div>
                  </div>
                )}

                {selectedRecord.resolved && (
                  <div className="border-t border-[#1E293B] pt-5">
                    <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-4">
                      <p className="text-xs text-emerald-400 font-semibold">✓ Resolved</p>
                      <p className="text-xs text-slate-400 mt-1">By: {selectedRecord.resolved_by}</p>
                      {selectedRecord.resolution_notes && (
                        <p className="text-xs text-slate-300 mt-2">{selectedRecord.resolution_notes}</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export default function ReviewQueue() {
  return (
    <Suspense fallback={<div className="glass-card p-10 text-center text-sm text-slate-400">Loading review queue...</div>}>
      <ReviewQueueContent />
    </Suspense>
  );
}
