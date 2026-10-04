import { CONFIG } from './config.js';

export async function apiFetch(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            cache: options.cache || 'no-store',
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options
        });
        if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
        return await response.json();
    } catch (error) {
        console.error(`API Error [${endpoint}]:`, error);
        return null;
    }
}

export const api = {
    getLogs: (filter, page, limit, date = '') => apiFetch(`/api/logs?filter=${filter}&page=${page}&limit=${limit}&date=${date}`),
    startEngine: (payload) => apiFetch('/api/start', { method: 'POST', body: JSON.stringify(payload) }),
    stopEngine: () => apiFetch('/api/stop', { method: 'POST' }),
    getSpyEyeAccount: () => apiFetch('/api/spyeye/account-info'),
    getSpyEyeHistorySyncStatus: () => apiFetch('/api/spyeye/history/sync-status'),
    getSpyEyeHistory: (filter, page, limit, date = '', sortOrder = 'new_first') => apiFetch(`/api/spyeye/history?date_filter=${encodeURIComponent(filter)}&page=${page}&limit=${limit}&date=${encodeURIComponent(date)}&sort_order=${encodeURIComponent(sortOrder)}`),
    syncSpyEye: (payload) => apiFetch('/api/spyeye/history/sync', { method: 'POST', body: JSON.stringify(payload) }),
    getGroupedOtp: () => apiFetch('/api/spyeye/grouped-otp-history'),
    get4SimBalance: () => apiFetch('/api/4sim/balance'),
    getOtpDoctorBalance: () => apiFetch('/api/otpdoctor/balance'),
    getTempOtpBalance: () => apiFetch('/api/tempotp/balance'),
    getTemporaSmsBalance: () => apiFetch('/api/temporasms/balance')
};
