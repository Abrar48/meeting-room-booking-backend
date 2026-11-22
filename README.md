# Meeting Room Booking System — Backend API

A production-grade RESTful backend service built with **Django** and **Django REST Framework (DRF)** for managing meeting room schedules, team booking requests, administrative approvals, and audit trails with strict role-based access control and concurrency locking.

---

## Tech Stack

- **Framework:** Python, Django, Django REST Framework (DRF)
- **Authentication:** JWT (`djangorestframework-simplejwt`) + Custom Token Verification Middleware
- **Database:** SQLite (Local Development) / PostgreSQL-ready
- **Code Quality & Linting:** Ruff (`ruff check .`)

---

## Implemented Features (Tasks 1 – 14)

1. **Project Architecture & Standardized Response Envelope:**
   - Modular app structure (`core`, `accounts`, `bookings`).
   - Unified JSON response structure (`{"status", "data", "message"}`) via `core/responses.py` and global exception handling (`400`, `401`, `403`, `404`, `409`) via `core/exceptions.py`.
2. **Data Modeling & Audit Trail:**
   - Custom `User` model with `ADMIN` and `TEAM_MEMBER` roles linked to `Team`.
   - `Booking` model tracking `PENDING`, `APPROVED`, `REJECTED`, and `CANCELLED` states in UTC.
   - `BookingAuditLog` model recording administrative state transitions (`APPROVED`, `REJECTED`, etc.) with actor, timestamps, and decision notes.
3. **Authentication & Role-Based Access Control (RBAC):**
   - JWT Login (`POST /api/auth/login/`) and current user profile (`GET /api/auth/me/`).
   - Custom permission guards (`requireAuth`, `requireAdmin`) and middleware enforcement.
4. **Time & Overlap Validation Engine:**
   - Reusable validation service (`bookings/services.py`) rejecting past timestamps and invalid ranges (`end_time <= start_time`).
   - Strict interval overlap detection (`startA < endB AND endA > startB`) against `APPROVED` bookings while allowing back-to-back boundaries (`endA == startB`).
   - Verified with automated unit tests (`python manage.py test bookings`).
5. **Public & Role-Aware Schedule API:**
   - `GET /api/bookings/schedule?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` returning confirmed (`APPROVED`) bookings while stripping private notes and requester details for regular team members.
6. **Team Member Booking Workflows:**
   - **Submit Request:** `POST /api/bookings/` validates time slots and overlaps, saving valid requests as `PENDING`.
   - **View Team Requests:** `GET /api/bookings/my-requests` returns team-scoped booking history, statuses, and admin decision notes with strict cross-team isolation.
   - **Cancel Own Request:** `PATCH /api/bookings/<id>/cancel` allows requesters to cancel their own `PENDING` requests using row-level locking.
7. **Admin Booking Management & Concurrency Safety:**
   - **List All Bookings:** `GET /api/admin/bookings` with filters for `status`, `start_date`, `end_date`, and `team_id`, exposing full requester details and notes.
   - **Approve Request:** `PATCH /api/admin/bookings/<id>/approve` uses `transaction.atomic()` and `select_for_update()` row-level locks to re-verify slot availability (`409 Conflict` on overlap), approve the booking, and log an audit entry.
   - **Reject Request:** `PATCH /api/admin/bookings/<id>/reject` marks `PENDING` requests as `REJECTED`, stores optional `decision_note`, and writes to `BookingAuditLog`.

---

## API Endpoints Overview

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health/` | Public | Service health check |
| `POST` | `/api/auth/login/` | Public | Authenticate user and obtain JWT tokens |
| `GET` | `/api/auth/me/` | Authenticated | Retrieve current user profile and role |
| `GET` | `/api/bookings/schedule` | Public / Role-aware | View confirmed room schedule (`APPROVED`) |
| `POST` | `/api/bookings/` | Team Member | Submit a new room booking request (`PENDING`) |
| `GET` | `/api/bookings/my-requests` | Team Member | List own team's booking requests & decision notes |
| `PATCH` | `/api/bookings/<id>/cancel` | Requester | Cancel own `PENDING` booking request |
| `GET` | `/api/admin/bookings` | Admin | List/filter all bookings with full requester info |
| `PATCH` | `/api/admin/bookings/<id>/approve` | Admin | Approve a `PENDING` request with concurrency lock |
| `PATCH` | `/api/admin/bookings/<id>/reject` | Admin | Reject a `PENDING` request with decision note |

---

## Local Setup & Running

```bash
# 1. Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Apply database migrations
python manage.py migrate

# 4. Run automated tests & linter
python manage.py test
ruff check .

# 5. Start development server
python manage.py runserver