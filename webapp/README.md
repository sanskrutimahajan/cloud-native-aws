# webapp

Cloud-native web application for CSYE 6225. Built with FastAPI and PostgreSQL, it provides RESTful APIs for health monitoring and user management with authentication, input validation, and secure password storage.

## Prerequisites

- Python 3.10 or higher
- PostgreSQL 16
- pip (Python package manager)
- Git

## Frameworks and Libraries

| Dependency | Purpose |
|---|---|
| FastAPI 0.104.1 | Web framework |
| Uvicorn 0.24.0 | ASGI server |
| SQLAlchemy 2.0.23 | ORM / database toolkit |
| psycopg2-binary 2.9.9 | PostgreSQL driver |
| bcrypt 4.1.1 | Password hashing |
| Pydantic 2.5.0 | Data validation (with email support) |
| python-dotenv 1.0.0 | Environment variable loading |
| pytest 7.4.3 | Test framework |
| httpx 0.25.2 | HTTP test client |
| pytest-cov 4.1.0 | Test coverage reporting |

All dependencies are listed in `requirements.txt`.

## Build and Deploy Instructions

### 1. Clone the repository

```bash
git clone git@github.com:Msanskruti/webapp_fork.git
cd webapp_fork
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up the database

Create a PostgreSQL database for the application:

```bash
createdb webapp_db
```

### 5. Configure environment variables

Create a `.env` file in the project root. Do not commit this file to version control.

Required environment variables:

- `DATABASE_HOST` - Database host 
- `DATABASE_PORT` - Database port 
- `DATABASE_NAME` - Database name
- `DATABASE_USER` - Database user
- `DATABASE_PASSWORD` - Database password
- `APP_HOST` - Application host (default: `0.0.0.0`)
- `APP_PORT` - Application port (default: `8080`)

### 6. Run the application

```bash
python run.py
```

The application will start on the host and port specified in your `.env` file (default: `http://localhost:8080`).

## API Endpoints

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | None | Health check with database connectivity verification |
| POST | `/v1/user` | None | Create a new user account |
| GET | `/v1/user/self` | Basic Auth | Retrieve authenticated user information |
| PUT | `/v1/user/self` | Basic Auth | Update authenticated user (first_name, last_name, password) |

## Testing

Tests use the same database configured via environment variables. Each test runs inside a transaction that is rolled back after completion, so no test data persists.

Run the full test suite:

```bash
pytest -v
```

Run tests with coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

Run a specific test file:

```bash
pytest tests/test_healthz.py -v
pytest tests/test_user.py -v
```
