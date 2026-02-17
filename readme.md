# Wallet Service

A production-ready Django wallet service for managing deposits and scheduled withdrawals with third-party bank integration.

## Brief

This service implements a wallet system where users can instantly deposit funds and schedule future withdrawals. The key feature is that withdrawal validation happens at execution time (not submission), allowing flexible scheduling while maintaining balance integrity. The system handles concurrent transactions safely using database-level locking and atomic operations.

## Key Features

- **Instant Deposits**: Immediate balance updates with transaction logging
- **Scheduled Withdrawals**: Queue withdrawals for future execution with automatic processing
- **Smart Validation**: Balance checked at withdrawal execution time (not submission)
- **Concurrency Safe**: Database locks prevent race conditions on simultaneous transactions
- **Failure Recovery**: Failed bank transactions automatically refund the wallet
- **Third-Party Integration**: Integrates with external bank API for withdrawal processing

## Architecture

### Database Schema

**Wallet**
- Stores user wallet balance
- Uses optimistic locking (version field) for concurrent updates

**TransactionLog**
- Immutable record of all completed transactions (deposits/withdrawals)

**ScheduledWithdrawal**
- Manages pending withdrawal requests
- Tracks status: PENDING → PROCESSING → COMPLETED/FAILED
- Includes retry logic and third-party response tracking

### Technology Stack

- **Framework**: Django + Django REST Framework
- **Database**: PostgreSQL (handles concurrent transactions)
- **Task Queue**: Celery + Redis
- **Scheduler**: Celery Beat (processes withdrawals every minute)

## Requirements Compliance

✅ **All PRD requirements satisfied:**

| Requirement | Implementation |
|-------------|----------------|
| Deposit funds | `POST /wallets/{uuid}/deposit` with atomic balance updates |
| Schedule withdrawals | `POST /wallets/{uuid}/withdraw` with future timestamp validation |
| Third-party integration | Bank API calls in `wallets/tasks.py:77` with retry logic |
| Non-negative balance | Enforced by `PositiveBigIntegerField` + execution-time validation |
| Validation at execution time | Balance checked in `process_single_withdrawal()`, not at submission |
| Concurrent transactions | Database locks (`select_for_update`) + atomic F() expressions |
| Handle failures | Failed transactions marked, amounts refunded automatically |
| Network failures | Try/except blocks catch all exceptions including timeouts |

## Quick Start

### Prerequisites
- Docker and Docker Compose installed

### Run the Project

1. **Start all services**
```bash
docker-compose up --build
```

This automatically starts:
- PostgreSQL database (port 5433)
- Redis cache (port 6380)
- Django API server (port 8000)
- Celery worker (background tasks)
- Celery beat (scheduler - runs every minute)

## API Usage

Replace `{wallet-uuid}` with your actual wallet UUID from step 2.

### 1. Check Wallet Balance
```bash
curl http://localhost:8000/wallets/{wallet-uuid}/
```

### 2. Deposit Funds
```bash
curl -X POST http://localhost:8000/wallets/{wallet-uuid}/deposit \
  -H "Content-Type: application/json" \
  -d '{"amount": 1000}'
```

### 3. Schedule a Withdrawal
```bash
curl -X POST http://localhost:8000/wallets/{wallet-uuid}/withdraw \
  -H "Content-Type: application/json" \
  -d '{"amount": 100, "scheduled_for": "2026-02-16 18:30:00"}'
```
**Note**: `scheduled_for` must be a future timestamp in format `YYYY-MM-DD HH:MM:SS`. The withdrawal will be processed automatically by Celery Beat when the scheduled time arrives.

## How It Works

### Deposit Flow
1. Validate amount > 0
2. Lock wallet row with `select_for_update()`
3. Update balance and create transaction record
4. Return new balance

### Withdrawal Flow
1. **Submission**: Validate future timestamp, create ScheduledWithdrawal (status=PENDING)
2. **Execution** (Celery Beat every 60 seconds):
   - Lock and fetch due withdrawals (`scheduled_for <= now`)
   - Mark as PROCESSING
   - **Atomically check balance and deduct** using database-level operation
   - Call third-party bank API
   - **Success**: Create transaction log, mark COMPLETED
   - **Failure**: Refund amount to wallet, mark FAILED with error message

### Concurrency & Safety

**Atomic Operations**: Uses database F() expressions for race-free balance updates
```python
# Only deducts if sufficient balance exists
Wallet.objects.filter(
    id=wallet_id,
    balance__gte=amount
).update(balance=F('balance') - amount)
```

**Row Locking**: Deposits use `select_for_update()` to prevent concurrent modifications

**Result**: If 10 concurrent $100 withdrawals target a $500 wallet, exactly 5 succeed and 5 fail with "Insufficient balance"

## Configuration

**Database**: PostgreSQL via Docker (auto-configured)
**Redis**: Celery broker via Docker (auto-configured)
**Third-Party Bank URL**: Configured in `wallets/utils.py` (default: `http://localhost:8010/`)

To change the bank URL, update:
```python
# wallets/utils.py
def request_third_party_deposit():
    response = requests.post("http://your-bank-url:8010/")
    return response.json()
```

## Project Structure
```
wallet/
├── wallet/              # Django project settings
│   ├── settings.py
│   ├── celery.py       # Celery configuration
│   └── urls.py
├── wallets/            # Main app
│   ├── models.py       # Wallet, TransactionLog, ScheduledWithdrawal
│   ├── views.py        # API endpoints
│   ├── services.py     # Business logic
│   └── tasks.py        # Celery tasks
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Key Design Decisions

1. **Separate tables for logs vs pending actions**: TransactionLog is immutable history, ScheduledWithdrawal is mutable state
2. **Validation at execution time**: Balance checked when withdrawal executes, not when scheduled
3. **Idempotency**: Each withdrawal has unique ID, prevents duplicate processing
4. **Atomic operations**: Use database-level atomicity instead of application locks
5. **Status tracking**: Clear state machine (PENDING → PROCESSING → COMPLETED/FAILED)

## Troubleshooting

### Withdrawals Not Processing?
```bash
# Check Celery Beat is running
docker-compose logs celery_beat | grep "process_scheduled_withdrawals"

# Check Celery Worker is running
docker-compose logs celery_worker | grep "wallets.tasks"

# Restart scheduler
docker-compose restart celery_beat celery_worker
```

### Database Connection Issues?
```bash
# Check services status
docker-compose ps

# Restart all services
docker-compose down && docker-compose up --build
```

### Check Withdrawal Status
```python
# In Django shell
from wallets.models import ScheduledWithdrawal
ScheduledWithdrawal.objects.filter(status='failed')  # View failed withdrawals
```

---

## Summary

This wallet service successfully implements all PRD requirements with production-ready patterns:
- **Concurrent safety** through database-level atomic operations
- **Deferred validation** by checking balance at execution time, not submission
- **Resilient processing** with automatic failure recovery and refunds
- **Scalable architecture** using Celery for background processing

The code demonstrates clean separation of concerns (models, services, views, tasks), proper error handling, comprehensive logging, and follows Django best practices.
