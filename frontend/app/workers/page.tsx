'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { getWorkers } from '@/lib/api';

export default function WorkerList() {
  const [workers, setWorkers] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const fetchWorkers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getWorkers({ search: search || undefined, page, limit: 50 });
      setWorkers(res.data.workers);
      setTotal(res.data.total);
    } catch {
      setWorkers([]);
    } finally {
      setLoading(false);
    }
  }, [search, page]);

  useEffect(() => {
    const timeout = setTimeout(fetchWorkers, search ? 300 : 0);
    return () => clearTimeout(timeout);
  }, [fetchWorkers, search]);

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Workers</h1>
          <p className="text-sm text-slate-500 mt-1">{total} registered workers</p>
        </div>
      </div>

      {/* Search */}
      <div className="glass-card p-4">
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="Search by name or phone..."
            className="input-field pl-10"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Worker ID</th>
                <th>Name</th>
                <th>Phone</th>
                <th>Role</th>
                <th>State</th>
                <th>Seniority</th>
                <th>Reviews</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j}><div className="h-4 w-16 shimmer rounded" /></td>
                    ))}
                  </tr>
                ))
              ) : workers.length === 0 ? (
                <tr>
                  <td colSpan={8} className="text-center py-12 text-slate-500">
                    {search ? 'No workers match your search' : 'No workers found. Run the pipeline first.'}
                  </td>
                </tr>
              ) : (
                workers.map((w) => (
                  <tr key={w.worker_id}>
                    <td className="font-mono text-xs text-blue-400">{w.worker_id}</td>
                    <td className="text-white text-xs font-medium">{w.name}</td>
                    <td className="font-mono text-xs">{w.phone}</td>
                    <td className="text-xs">{w.role}</td>
                    <td className="text-xs">{w.state}</td>
                    <td>
                      <span className={`badge ${w.seniority === 'senior' ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-500/20 text-slate-400'}`}>
                        {w.seniority}
                      </span>
                    </td>
                    <td>
                      {w.review_count > 0 ? (
                        <span className="badge bg-amber-500/20 text-amber-400">{w.review_count}</span>
                      ) : (
                        <span className="text-xs text-slate-600">0</span>
                      )}
                    </td>
                    <td>
                      <Link
                        href={`/workers/${w.worker_id}`}
                        className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                      >
                        View →
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {total > 50 && (
          <div className="flex items-center justify-between p-4 border-t border-[#1E293B]">
            <span className="text-xs text-slate-500">Page {page} of {Math.ceil(total / 50)}</span>
            <div className="flex gap-2">
              <button className="btn btn-ghost text-xs py-1.5 px-3" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
              <button className="btn btn-ghost text-xs py-1.5 px-3" disabled={page >= Math.ceil(total / 50)} onClick={() => setPage(page + 1)}>Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
