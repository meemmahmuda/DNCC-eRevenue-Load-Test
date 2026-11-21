# DNCC e-Revenue Login Flow – Locust Load Test

Load test of the **DNCC e-Revenue** login journey (unlock user → login form → dropdown selection → credentials → OTP → dashboard), written with [Locust](https://locust.io/).


## Test Summary

| Item | Value |
| --- | --- |
| Target host | `https://erevenue.dncc.gov.bd` |
| Script | `locustfile.py` (user class: `DNCCUser`, task: `login`) |
| Date (UTC) | 2026-11-11, 06:49:16 – 06:49:47 |
| Duration | 31 seconds |
| Peak virtual users | 10 (ramped up from 1 over ~11 s) |
| Total requests | 965 |
| Failed requests | 58 (≈ 6.0 %) |
| Aggregated throughput | ≈ 31 req/s average, ≈ 35 req/s at steady state |
| Median / 95th / 99th percentile | 18 ms / 170 ms / 400 ms |
| Average / max response time | 43.65 ms / 1082 ms |

## Results per Step

| # | Step | Requests | Failures | Avg (ms) | 95th % (ms) | Max (ms) |
| - | ---- | -------: | -------: | -------: | ----------: | -------: |
| 01 | Unlock User – `GET /web/userulocknew.aspx` | 153 | 0 | 36.64 | 82 | 315 |
| 02 | Load Login Form – `GET /newv/Default` | 153 | 0 | 14.89 | 28 | 326 |
| 03 | Select Dropdowns – `POST /newv/Default` | 153 | 0 | 12.69 | 21 | 44 |
| 04 | Submit Login Credentials – `POST /newv/Default` | 153 | **35** | 70.03 | 160 | 619 |
| 05 | Open OTP Page – `GET /newv/otpverification.aspx` | 118 | 0 | 24.91 | 43 | 403 |
| 06 | Verify OTP – `POST /newv/otpverification.aspx` | 118 | 0 | 11.18 | 23 | 44 |
| 07 | Access Dashboard – `GET /newv/web/homenew_ver2` | 117 | **23** | 148.10 | 450 | 1082 |

## Failures

| Count | Step | Error |
| ----: | ---- | ----- |
| 35 | 04 – Submit Login Credentials | `Login failed: status=200, msg=['alert: Invalid Session / Inappropriate Logout']` |
| 23 | 07 – Access Dashboard | `Session invalid, redirected to: /newv/web/success.aspx` |

## Observations

- All failures come from **session handling** (steps 04 and 07), not from slow servers or timeouts. There were no Python exceptions.
- The "Invalid Session / Inappropriate Logout" message suggests the application invalidates a session when the same account logs in more than once at the same time. If several virtual users share one account, using a separate account per user is worth trying.
- The dashboard page (step 07) is the heaviest: ≈ 67 KB per response and the highest latency (avg 148 ms, p99 740 ms).
- Steps 01–03 and 05–06 were fast (average under 40 ms) and error-free at 10 concurrent users.
- This was a short, small test (31 s, 10 users), so treat it as a smoke test, not a capacity measurement.

## Screenshots

### Request statistics
![Request statistics](docs/screenshots/01-request-statistics.png)

### Response time statistics
![Response time statistics](docs/screenshots/02-response-time-statistics.png)

### Failures
![Failures statistics](docs/screenshots/03-failures-statistics.png)

### Charts (RPS, response times, users)
![Charts](docs/screenshots/04-charts.png)

Full page: [`docs/screenshots/00-full-report.png`](docs/screenshots/00-full-report.png)

## Project Structure

```
.
├── locustfile.py            # Locust test scenario
├── docs/
│   ├── report.html          # Original Locust HTML report (open in a browser)
│   └── screenshots/         # Screenshots used in this README
└── README.md
```

## How to Run

```bash
# 1. Install Locust
pip install locust

# 2. Interactive mode (web UI at http://localhost:8089)
locust -f locustfile.py --host https://erevenue.dncc.gov.bd

# 3. Headless mode with an HTML report (same settings as this report)
locust -f locustfile.py --host https://erevenue.dncc.gov.bd \
       --headless -u 10 -r 1 -t 30s --html docs/report.html
```

Put credentials in environment variables or a git-ignored file (for example `.env`), not in the code.

## Test Scenario

Each virtual user (`DNCCUser`) runs one `login` task with these steps in order:

1. Unlock user
2. Load login form
3. Select dropdowns
4. Submit login credentials
5. Open OTP page
6. Verify OTP
7. Access dashboard

## Next Steps

- Use a unique account per virtual user to remove session collisions.
- Increase users and duration gradually (for example 10 → 50 → 100) to find the breaking point.
- Re-run after the session issue is fixed and compare against this baseline.
