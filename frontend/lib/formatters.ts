/**
 * Formatting utilities for the wage reconciliation platform.
 * All monetary values are in paise (1 INR = 100 paise).
 */

export function formatPaise(paise: number | null | undefined): string {
  if (paise === null || paise === undefined) return '₹0.00';
  const inr = paise / 100;
  return `₹${inr.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatDelta(delta: number | null | undefined): { text: string; color: string; bg: string } {
  if (delta === null || delta === undefined) return { text: '₹0.00', color: 'text-gray-400', bg: 'bg-gray-500/10' };
  const abs = Math.abs(delta);
  const formatted = formatPaise(abs);

  if (delta === 0) {
    return { text: '₹0.00', color: 'text-emerald-400', bg: 'bg-emerald-500/10' };
  } else if (delta > 0) {
    return { text: `+${formatted}`, color: 'text-emerald-400', bg: 'bg-emerald-500/10' };
  } else {
    return { text: `-${formatted}`, color: 'text-red-400', bg: 'bg-red-500/10' };
  }
}

export function formatPeriod(period: string): string {
  if (!period) return '';
  const [year, month] = period.split('-');
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[parseInt(month) - 1]} ${year}`;
}

export function formatConfidence(score: number | null | undefined): { text: string; color: string } {
  if (score === null || score === undefined) return { text: 'N/A', color: 'text-gray-400' };
  const pct = (score * 100).toFixed(0);
  if (score >= 0.9) return { text: `${pct}%`, color: 'text-emerald-400' };
  if (score >= 0.7) return { text: `${pct}%`, color: 'text-yellow-400' };
  return { text: `${pct}%`, color: 'text-red-400' };
}

export function getPriorityBadge(priority: string | null | undefined): { text: string; classes: string } {
  switch (priority) {
    case 'P0': return { text: 'P0 CRITICAL', classes: 'bg-red-500/20 text-red-400 border border-red-500/30' };
    case 'P1': return { text: 'P1 HIGH', classes: 'bg-orange-500/20 text-orange-400 border border-orange-500/30' };
    case 'P2': return { text: 'P2 MEDIUM', classes: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' };
    case 'P3': return { text: 'P3 LOW', classes: 'bg-blue-500/20 text-blue-400 border border-blue-500/30' };
    default: return { text: priority || '—', classes: 'bg-gray-500/20 text-gray-400' };
  }
}

export function getTypeBadge(type: string | null | undefined): { text: string; classes: string } {
  switch (type) {
    case 'EXACT_MATCH': return { text: 'Exact Match', classes: 'bg-emerald-500/20 text-emerald-400' };
    case 'NEAR_MATCH': return { text: 'Near Match', classes: 'bg-blue-500/20 text-blue-400' };
    case 'UNDERPAYMENT': return { text: 'Underpayment', classes: 'bg-red-500/20 text-red-400' };
    case 'OVERPAYMENT': return { text: 'Overpayment', classes: 'bg-amber-500/20 text-amber-400' };
    case 'UNMATCHED_WORK': return { text: 'Unmatched Work', classes: 'bg-purple-500/20 text-purple-400' };
    case 'UNMATCHED_PAYMENT': return { text: 'Unmatched Payment', classes: 'bg-pink-500/20 text-pink-400' };
    case 'DUPLICATE_PAYMENT': return { text: 'Duplicate Payment', classes: 'bg-orange-500/20 text-orange-400' };
    default: return { text: type || '—', classes: 'bg-gray-500/20 text-gray-400' };
  }
}
