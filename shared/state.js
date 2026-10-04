class GlobalState {
    constructor() {
        this.listeners = [];
        this.data = {
            total_targeted: 0,
            total_thread_count: 0,
            total_secured: 0,
            success_otps: 0,
            already_registered: 0,
            cancelled_orders: 0,
            realtime_active_threads: 0,
            realtime_already_logs: 0,
            cancel_failed_logs: 0,
            cancel_logs: [],
            history_sheet_sync_last: null,
            history_sheet_sync_new: 0,
            history_sheet_sync_error: null,
            system_status: "Ready to Start",
            progress: 0,
            eta: "---",
            game_analytics: {},
            registration_summary: {},
            error_logs: [],
            activity_timeline: [],
            recent_activity: [],
            success_records: [],
            live_success_records: []
        };
    }

    getState() {
        return this.data;
    }

    setState(newState) {
        this.data = { ...this.data, ...newState };
        this.notify();
    }

    subscribe(listener) {
        this.listeners.push(listener);
    }

    notify() {
        this.listeners.forEach(listener => listener(this.data));
    }
}

export const appState = new GlobalState();
