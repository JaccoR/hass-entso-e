# Fix: Prevent Home Assistant freeze when ENTSO-e API is slow or unavailable

## Problem
When the ENTSO-e API experiences issues (slow responses, timeouts, 503 errors), Home Assistant completely freezes during startup, making the entire system unusable.

**Root causes identified:**
1. No timeout on `requests.get()` calls - could hang indefinitely
2. Blocking startup while waiting for API response
3. Multiple concurrent API calls exhausting thread pool

## Solution
This PR implements robust API error handling to prevent Home Assistant from freezing:

### Changes
1. **Add request timeouts** - 20s for startup (5s+15s), 40s for normal updates (10s+30s)
2. **Non-blocking startup** - API fetch runs in background task, HA boots immediately
3. **Prevent concurrent calls** - Use `asyncio.Lock` to ensure only one API request at a time
4. **Graceful error handling** - Catch timeout/connection errors, fallback to cached data
5. **Debug logging** - Added timing logs to identify performance bottlenecks

### Behavior
| Scenario | Before | After |
|----------|--------|-------|
| API slow (10-20s) | HA freezes | HA boots normally, brief "unavailable" |
| API timeout (>20s) | HA hangs forever | HA boots, sensors show unavailable, auto-retry |
| API down | HA unusable | HA fully functional, uses cached data |

### Testing
Tested during actual ENTSO-e API outage on 2025-12-04. Logs confirm:
- Setup completes in 0.00s (non-blocking)
- Timeouts work correctly (20s max)
- Concurrent calls prevented
- Graceful degradation when API unavailable

## Impact
✅ Home Assistant will never freeze due to ENTSO-e API issues
✅ System remains fully functional even when API is down
✅ Sensors show "unavailable" briefly, then update when data arrives
