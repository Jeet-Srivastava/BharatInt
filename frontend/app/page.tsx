'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { getDashboardStats, triggerPipeline, getPipelineRun } from '@/lib/api';
import { formatPaise, formatCompactPaise, formatDelta, formatPeriod, getPriorityBadge, getTypeBadge } from '@/lib/formatters';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell
} from 'recharts';

const CHART_COLORS = ['#EF4444', '#F59E0B', '#3B82F6', '#10B981', '#8B5CF6', '#EC4899', '#FF8C00'];

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelineMessage, setPipelineMessage] = useState('');
  const [error, setError] = useState('');

  const fetchStats = useCallback(async () => {
    try {
      const res = await getDashboardStats();
      setStats(res.data);
      setError('');
    } catch (err: any) {
      setError('Failed to load dashboard data. Run the pipeline first.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  const handleRunPipeline = async () => {
    setPipelineRunning(true);
    setPipelineMessage('Triggering pipeline...');
    try {
      const res = await triggerPipeline();
      const runId = res.data.run_id;
      setPipelineMessage(`Pipeline started (${runId.slice(0, 8)}…). Processing...`);

      // Poll status every 3s
      const pollInterval = setInterval(async () => {
        try {
          const status = await getPipelineRun(runId);
          if (status.data.status === 'completed') {
            clearInterval(pollInterval);
            setPipelineMessage(`✅ Pipeline complete! Logs: ${status.data.rows_logs}, Transfers: ${status.data.rows_transfers}, Anomalies: ${status.data.anomalies_found}`);
            setPipelineRunning(false);
            fetchStats();
          } else if (status.data.status === 'failed') {
            clearInterval(pollInterval);
            setPipelineMessage(`❌ Pipeline failed: ${status.data.error_message}`);
            setPipelineRunning(false);
          }
        } catch {
          // keep polling
        }
      }, 3000);
    } catch (err: any) {
      setPipelineMessage(`❌ Failed to trigger pipeline: ${err.message}`);
      setPipelineRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-4 gap-5">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="glass-card p-6 h-[120px] shimmer" />
          ))}
        </div>
        <div className="grid grid-cols-2 gap-5">
          <div className="glass-card p-6 h-[400px] shimmer" />
          <div className="glass-card p-6 h-[400px] shimmer" />
        </div>
      </div>
    );
  }

  const delta = stats ? formatDelta(stats.net_delta_paise) : { text: '—', color: '', bg: '' };

  const barData = stats?.period_breakdown?.map((p: any) => ({
    name: formatPeriod(p.period),
    Expected: p.expected_paise,
    Actual: p.actual_paise,
  })) || [];

  const pieData = stats?.discrepancy_breakdown?.map((d: any) => ({
    name: d.type.replace('_', ' '),
    value: d.count,
  })) || [];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Pipeline Controls */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Reconciliation Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Wage payout analysis across all billing periods</p>
        </div>
        <div className="flex items-center gap-4">
          {pipelineMessage && (
            <span className="text-xs text-slate-400 max-w-[400px] truncate">{pipelineMessage}</span>
          )}
          <button
            onClick={handleRunPipeline}
            disabled={pipelineRunning}
            className={`btn ${pipelineRunning ? 'btn-ghost opacity-50 cursor-wait' : 'btn-accent'}`}
          >
            {pipelineRunning ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Running...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                Run Pipeline
              </>
            )}
          </button>
        </div>
      </div>

      {error && !stats ? (
        <div className="glass-card p-12 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-blue-500/10 flex items-center justify-center">
            <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7C5 4 4 5 4 7z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.5 2.5v4M9.5 2.5v4M4 11h16" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">No Data Yet</h3>
          <p className="text-sm text-slate-400 mb-6">Click &quot;Run Pipeline&quot; to ingest the CSV files and generate reconciliation data.</p>
          <button onClick={handleRunPipeline} disabled={pipelineRunning} className="btn btn-accent">
            Run Pipeline Now
          </button>
        </div>
      ) : stats && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {/* Total Expected */}
            <div className="glass-card glass-card-hover p-6 glow-blue">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Expected</span>
                <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </div>
              </div>
              <p className="text-2xl font-bold text-white">{formatPaise(stats.total_expected_paise)}</p>
              <p className="text-xs text-slate-500 mt-1">{stats.total_records} records processed</p>
            </div>

            {/* Total Actual */}
            <div className="glass-card glass-card-hover p-6 glow-green">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Total Actual Paid</span>
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
              </div>
              <p className="text-2xl font-bold text-white">{formatPaise(stats.total_actual_paise)}</p>
              <p className="text-xs text-slate-500 mt-1">{stats.total_workers} workers</p>
            </div>

            {/* Net Delta */}
            <div className={`glass-card glass-card-hover p-6 ${stats.net_delta_paise < 0 ? 'glow-red' : 'glow-green'}`}>
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Net Delta</span>
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${stats.net_delta_paise < 0 ? 'bg-red-500/10' : 'bg-emerald-500/10'}`}>
                  <svg className={`w-4 h-4 ${stats.net_delta_paise < 0 ? 'text-red-400' : 'text-emerald-400'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                </div>
              </div>
              <p className={`text-2xl font-bold ${delta.color}`}>{delta.text}</p>
              <p className="text-xs text-slate-500 mt-1">
                {stats.net_delta_paise < 0 ? 'Net underpayment detected' : stats.net_delta_paise > 0 ? 'Net overpayment detected' : 'Balanced'}
              </p>
            </div>

            {/* Open Reviews */}
            <div className="glass-card glass-card-hover p-6 glow-orange">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Open Reviews</span>
                <div className="w-8 h-8 rounded-lg bg-orange-500/10 flex items-center justify-center">
                  <svg className="w-4 h-4 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
              </div>
              <p className="text-2xl font-bold text-white">{stats.unresolved_count}</p>
              <div className="flex gap-2 mt-2">
                {stats.review_count_by_priority?.map((p: any) => {
                  const badge = getPriorityBadge(p.priority);
                  return (
                    <span key={p.priority} className={`badge ${badge.classes}`}>
                      {p.priority}: {p.count}
                    </span>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
            {/* Bar Chart */}
            <div className="glass-card p-6 lg:col-span-2">
              <h3 className="text-sm font-semibold text-white mb-4">Expected vs Actual by Period</h3>
              <div className="h-[340px]">
                {barData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={barData} barGap={4}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="name" tick={{ fill: '#64748B', fontSize: 11 }} axisLine={{ stroke: '#1E293B' }} />
                      <YAxis
                        tick={{ fill: '#64748B', fontSize: 11 }}
                        axisLine={{ stroke: '#1E293B' }}
                        tickFormatter={(value) => formatCompactPaise(Number(value))}
                      />
                      <Tooltip
                        contentStyle={{ background: '#1A2332', border: '1px solid #1E293B', borderRadius: '8px', color: '#F1F5F9', fontSize: '12px' }}
                        formatter={(value: number) => [formatPaise(value), '']}
                      />
                      <Legend wrapperStyle={{ fontSize: '12px', color: '#94A3B8' }} />
                      <Bar dataKey="Expected" fill="#3B82F6" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="Actual" fill="#10B981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-500 text-sm">No period data available</div>
                )}
              </div>
            </div>

            {/* Donut Chart */}
            <div className="glass-card p-6">
              <h3 className="text-sm font-semibold text-white mb-4">Discrepancy Breakdown</h3>
              <div className="h-[260px]">
                {pieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%" cy="50%"
                        innerRadius={60} outerRadius={95}
                        dataKey="value"
                        stroke="none"
                      >
                        {pieData.map((_: any, idx: number) => (
                          <Cell key={idx} fill={CHART_COLORS[idx % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ background: '#1A2332', border: '1px solid #1E293B', borderRadius: '8px', color: '#F1F5F9', fontSize: '12px' }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex items-center justify-center h-full text-slate-500 text-sm">No data</div>
                )}
              </div>
              <div className="space-y-2 mt-2">
                {pieData.map((d: any, idx: number) => (
                  <div key={d.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-2.5 h-2.5 rounded-full" style={{ background: CHART_COLORS[idx % CHART_COLORS.length] }} />
                      <span className="text-slate-400">{d.name}</span>
                    </div>
                    <span className="text-white font-medium">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Quick Review Queue */}
          <div className="glass-card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-white">Priority Review Items</h3>
              <Link href="/review" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                View All →
              </Link>
            </div>
            <div className="flex gap-3 flex-wrap">
              {stats.review_count_by_priority?.map((p: any) => {
                const badge = getPriorityBadge(p.priority);
                return (
                  <Link
                    key={p.priority}
                    href={`/review?priority=${p.priority}`}
                    className="glass-card glass-card-hover p-4 flex-1 min-w-[140px]"
                  >
                    <span className={`badge ${badge.classes} mb-2`}>{badge.text}</span>
                    <p className="text-2xl font-bold text-white mt-2">{p.count}</p>
                    <p className="text-xs text-slate-500">items to review</p>
                  </Link>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
