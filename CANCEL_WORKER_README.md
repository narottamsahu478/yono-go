# Dedicated cancellation worker

- Supports 4SIM, TempOTP, OTPDoctor and TemporaSMS using the original provider cancellation logic.
- Transaction IDs are stored when numbers are bought in SQLite (`CANCEL_DB_PATH`, default `data/cancel_worker.sqlite3`).
- Only explicit cancellation requests enter the retry queue; merely buying a number does not make it eligible for cancellation.
- Worker checks every 10 seconds, with backoff after failed attempts.
- OTP-received activations are marked protected; no cancellation is requested for those records.
- Start via the existing FastAPI lifespan (`main.py`).
- For Railway, configure `CANCEL_DB_PATH=/data/cancel_worker.sqlite3` and mount a persistent volume at `/data`.
- Run ONE app process/replica with this embedded worker. Multiple workers/processes require additional cross-process coordination and an external DB.
- Review existing license startup behavior and provider API credentials before deployment; these were not changed.
- Existing provider cancel routine may report ambiguous statuses for some API responses. Validate with provider test transactions before production deployment.
