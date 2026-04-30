'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getWorkerAuditTrail } from '@/lib/api';
import { formatPaise, formatDelta, formatPeriod, getTypeBadge, getPriorityBadge, formatConfidence } from '@/lib/formatters';

export default function WorkerDrilldown() {
  const params = useParams();
  const workerId = params.id as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
      try {
        const res = await getWorkerAuditTrail(workerId);
        setData(res.data);
      } catch {
        setData(null);
      }
      setLoading(false);
    }
    fetch();
  }, [workerId]);

  if (loading) {
    return (
      <div className="space-y-6">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="glass-card p-6 h-[200px] shimmer" />
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-card p-12 text-center">
        <p className="text-slate-400">Worker not found.</p>
        <Link href="/workers" className="text-sm text-blue-400 hover:text-blue-300 mt-4 inline-block">
          ← Back to Workers
        </Link>
      </div>
    );
  }

  const worker = data.worker;
  const shifts = data.shifts || [];
  const transfers = data.transfers || [];
  const reconciliation = data.reconciliation || [];
  const identityConfidence = formatConfidence(worker.identity_confidence);
  const identityConfidenceFloor = formatConfidence(worker.identity_confidence_floor);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Link href="/workers" className="hover:text-slate-300 transition-colors">Workers</Link>
        <span>/</span>
        <span className="text-slate-300">{worker.name}</span>
      </div>

      {/* Identity Card */}
      <div className="glass-card p-6">
        <div className="flex items-start gap-5">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
            <span className="text-white text-lg font-bold">
              {worker.name?.charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">{worker.name}</h1>
            <p className="text-sm text-slate-400 mt-0.5 font-mono">{worker.worker_id}</p>
            <div className="flex flex-wrap gap-4 mt-3">
              <div className="text-xs">
                <span className="text-slate-500">Phone:</span>
                <span className="text-white ml-1 font-mono">{worker.phone}</span>
              </div>
              <div className="text-xs">
                <span className="text-slate-500">Role:</span>
                <span className="text-white ml-1">{worker.role}</span>
              </div>
              <div className="text-xs">
                <span className="text-slate-500">State:</span>
                <span className="text-white ml-1">{worker.state}</span>
              </div>
              <div className="text-xs">
                <span className="text-slate-500">Seniority:</span>
                <span className={`ml-1 badge ${worker.seniority === 'senior' ? 'bg-purple-500/20 text-purple-400' : 'bg-slate-500/20 text-slate-400'}`}>
                  {worker.seniority}
                </span>
              </div>
              <div className="text-xs">
                <span className="text-slate-500">Registered:</span>
                <span className="text-white ml-1">{worker.registered_on}</span>
              </div>
              <div className="text-xs">
                <span className="text-slate-500">Identity Confidence:</span>
                <span className={`ml-1 ${identityConfidence.color}`}>{identityConfidence.text}</span>
                {worker.identity_confidence_floor !== null && worker.identity_confidence_floor !== undefined && (
                  <span className="text-slate-500 ml-2">floor {identityConfidenceFloor.text}</span>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Per-Period Reconciliation */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-white mb-4">Reconciliation Summary</h2>
        {reconciliation.length === 0 ? (
          <p className="text-xs text-slate-500">No reconciliation data. Run the pipeline first.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Expected</th>
                  <th>Actual</th>
                  <th>Delta</th>
                  <th>Type</th>
                  <th>Priority</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {reconciliation.map((r: any) => {
                  const d = formatDelta(r.delta_paise);
                  const type = getTypeBadge(r.discrepancy_type);
                  const priority = getPriorityBadge(r.priority);
                  const conf = formatConfidence(r.confidence_score);
                  return (
                    <tr key={r.id}>
                      <td className="text-xs font-medium text-white">{formatPeriod(r.billing_period)}</td>
                      <td className="text-xs font-mono">{formatPaise(r.expected_paise)}</td>
                      <td className="text-xs font-mono">{formatPaise(r.actual_paise)}</td>
                      <td className={`text-xs font-mono font-semibold ${d.color}`}>{d.text}</td>
                      <td><span className={`badge ${type.classes}`}>{type.text}</span></td>
                      <td><span className={`badge ${priority.classes}`}>{priority.text}</span></td>
                      <td className={`text-xs ${conf.color}`}>{conf.text}</td>
                      <td>
                        {r.resolved ? (
                          <span className="badge bg-emerald-500/20 text-emerald-400">Resolved</span>
                        ) : r.needs_manual_review ? (
                          <span className="badge bg-amber-500/20 text-amber-400">Review</span>
                        ) : (
                          <span className="badge bg-slate-500/20 text-slate-400">OK</span>
                        )}
                      </td>
                      <td>
                        <Link href={`/review?recordId=${r.id}`} className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                          Review →
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Shifts Timeline */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-white mb-4">
          Shift Timeline <span className="text-slate-500 font-normal">({shifts.length} shifts)</span>
        </h2>
        {shifts.length === 0 ? (
          <p className="text-xs text-slate-500">No shifts recorded.</p>
        ) : (
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Log ID</th>
                  <th>Date</th>
                  <th>Hours</th>
                  <th>Vendor</th>
                  <th>Supervisor</th>
                  <th>Rate</th>
                  <th>Expected</th>
                  <th>Confidence</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {shifts.map((s: any) => {
                  const conf = formatConfidence(s.identity_confidence);
                  return (
                    <tr key={s.log_id}>
                      <td className="text-xs font-mono text-blue-400">{s.log_id}</td>
                      <td className="text-xs">{s.work_date}</td>
                      <td className={`text-xs font-mono ${s.hours_anomaly ? 'text-red-400 font-bold' : ''}`}>{s.hours}h</td>
                      <td className="text-xs">{s.vendor_app}</td>
                      <td className="text-xs">{s.supervisor_id}</td>
                      <td className="text-xs font-mono">
                        {s.rate_paise ? formatPaise(s.rate_paise) : s.rate_status}
                      </td>
                      <td className="text-xs font-mono text-emerald-400">
                        {s.expected_paise ? formatPaise(s.expected_paise) : '—'}
                      </td>
                      <td className={`text-xs ${conf.color}`}>{conf.text}</td>
                      <td>
                        <div className="flex gap-1 flex-wrap">
                          {s.tz_corrected && <span className="badge bg-amber-500/20 text-amber-400 text-[10px]">TZ</span>}
                          {s.hours_anomaly && <span className="badge bg-red-500/20 text-red-400 text-[10px]">Anomaly</span>}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Transfers */}
      <div className="glass-card p-6">
        <h2 className="text-sm font-semibold text-white mb-4">
          Bank Transfers <span className="text-slate-500 font-normal">({transfers.length} UTRs)</span>
        </h2>
        {transfers.length === 0 ? (
          <p className="text-xs text-slate-500">No transfers recorded.</p>
        ) : (
          <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>UTR</th>
                  <th>Date</th>
                  <th>Period</th>
                  <th>Amount</th>
                  <th>Account</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {transfers.map((t: any) => (
                  <tr key={t.utr}>
                    <td className="text-xs font-mono text-blue-400">{t.utr}</td>
                    <td className="text-xs">{t.transfer_date}</td>
                    <td className="text-xs">{formatPeriod(t.billing_period)}</td>
                    <td className="text-xs font-mono text-emerald-400">{formatPaise(t.amount_paise)}</td>
                    <td className="text-xs font-mono">****{t.account_last4}</td>
                    <td>
                      <div className="flex gap-1 flex-wrap">
                        {t.precision_bug && <span className="badge bg-amber-500/20 text-amber-400 text-[10px]">Precision Bug</span>}
                        {t.low_value && <span className="badge bg-red-500/20 text-red-400 text-[10px]">Low Value</span>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
