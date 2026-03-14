/**
 * Shared API helpers for the UK Climate Insights dashboard.
 * All fetch calls hit the FastAPI backend at the same origin.
 */

export const BASE = '';

export async function apiFetch(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getStations() {
  const res = await apiFetch('/stations?limit=100');
  // API returns PaginatedResponse: { data: [...], pagination: {...} }
  return Array.isArray(res) ? res : (res.data || res.items || []);
}

export async function getStation(id) {
  return apiFetch(`/stations/${id}`);
}

export async function getExtremes() {
  return apiFetch('/analytics/extremes');
}

export async function getSeasonal(stationId, variable, yearFrom, yearTo) {
  return apiFetch(`/analytics/seasonal/${stationId}?variable=${variable}&year_from=${yearFrom}&year_to=${yearTo}`);
}

export async function getTrends(stationId, variable, dateFrom, dateTo) {
  return apiFetch(`/analytics/trends/${stationId}?variable=${variable}&date_from=${dateFrom}&date_to=${dateTo}`);
}

export async function getAnomalies(stationId, variable, sigma) {
  return apiFetch(`/analytics/anomalies/${stationId}?variable=${variable}&threshold_sigma=${sigma}`);
}

export async function getHeatmap(stationId, variable, year) {
  return apiFetch(`/analytics/heatmap/${stationId}?variable=${variable}&year=${year}`);
}

export async function getClimateNormal(stationId) {
  return apiFetch(`/analytics/climate-normal/${stationId}`);
}

export async function getCompare(stationIds, variable, dateFrom, dateTo) {
  return apiFetch(`/analytics/compare?stations=${stationIds.join(',')}&variable=${variable}&date_from=${dateFrom}&date_to=${dateTo}`);
}

// ── Chart.js default dark theme ─────────────────────────────────────────────
export const CHART_DEFAULTS = {
  color: '#8b92b4',
  borderColor: '#2e3251',
  backgroundColor: 'rgba(79,142,247,0.15)',
};

export function applyDarkTheme() {
  if (typeof Chart === 'undefined') return;
  Chart.defaults.color = '#8b92b4';
  Chart.defaults.borderColor = '#2e3251';
  Chart.defaults.backgroundColor = 'rgba(79,142,247,0.15)';
  Chart.defaults.plugins.legend.labels.color = '#8b92b4';
  Chart.defaults.plugins.tooltip.backgroundColor = '#1a1d27';
  Chart.defaults.plugins.tooltip.borderColor = '#2e3251';
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.titleColor = '#e2e6f3';
  Chart.defaults.plugins.tooltip.bodyColor = '#8b92b4';
  Chart.defaults.scale = {
    ...Chart.defaults.scale,
    grid: { color: '#2e3251' },
    ticks: { color: '#8b92b4' },
  };
}

export const PALETTE = [
  '#4f8ef7', '#34c78a', '#f5c842', '#f05858',
  '#a78bfa', '#fb923c', '#22d3ee', '#f472b6',
];

export const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

/** Format a date string as "15 Jun 2020" */
export function fmtDate(d) {
  if (!d) return '—';
  const dt = new Date(d);
  return dt.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

/** Show loading text inside an element */
export function setLoading(el, msg = 'Loading…') {
  el.innerHTML = `<p class="loading">${msg}</p>`;
}

/** Show error text inside an element */
export function setError(el, msg) {
  el.innerHTML = `<p class="error-msg">⚠ ${msg}</p>`;
}

/** Populate a <select> with station options */
export function populateStationSelect(sel, stations, valueField = 'station_id') {
  sel.innerHTML = '';
  stations.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s[valueField];
    opt.textContent = `${s.name} (${s.station_id})`;
    sel.appendChild(opt);
  });
}
