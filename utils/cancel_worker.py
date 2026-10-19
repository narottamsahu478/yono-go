"""Single-process dedicated cancel consumer; uses the existing provider cancel routine."""
import asyncio
import logging
import globals
from utils import cancel_registry as registry

log = logging.getLogger(__name__)

async def run_cancel_worker():
    from utils.helpers import terminate_gateway_order_async
    while True:
        try:
            registry.recover()
            item = registry.claim()
            if not item:
                await asyncio.sleep(10)
                continue
            provider, txn_id, phone, attempts = item
            # The existing routine reads global_provider. Switching is safe only
            # while provider-specific cancellation is serialized by the shared lock.
            if registry.is_protected(provider, txn_id):
                continue
            async with globals.cancel_worker_lock:
                old_provider = globals.global_provider
                try:
                    globals.global_provider = provider
                    result = await terminate_gateway_order_async(txn_id, False, phone, True, _worker=True)
                finally:
                    globals.global_provider = old_provider
            registry.finish(provider, txn_id, result, attempts)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception('Dedicated cancel worker error')
            await asyncio.sleep(10)
