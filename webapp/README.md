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

## Automated Setup (Ubuntu 24.04 LTS)

The `scripts/setup.sh` script automates the complete setup on a fresh Ubuntu 24.04 LTS server. It performs the following steps:

1. Updates and upgrades system packages
2. Installs and enables PostgreSQL
3. Creates the application database and database user
4. Installs Python 3, pip, and venv
5. Creates a dedicated Linux group and user (`csye6225`)
6. Deploys application files to `/opt/csye6225/`
7. Sets up a Python virtual environment and installs dependencies
8. Sets file ownership and permissions
9. Verifies the installation

### Usage
```bash
git clone git@github.com:YOUR_USERNAME/webapp_fork.git
cd webapp_fork
sudo bash scripts/setup.sh
```

After setup completes, update the database password in `/opt/csye6225/.env`, then start the application:
```bash
sudo -u csye6225 /opt/csye6225/venv/bin/python /opt/csye6225/run.py
```

## Manual Setup (Development)

### 1. Clone the repository
```bash
git clone git@github.com:YOUR_USERNAME/webapp_fork.git
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
| GET | `/v1/metadata` | None | Instance metadata (auto-detects AWS/GCP) |
| POST | `/v1/user` | None | Create a new user account |
| GET | `/v1/user/self` | Basic Auth | Retrieve authenticated user information |
| PUT | `/v1/user/self` | Basic Auth | Update authenticated user (first_name, last_name, password) |

## Packer - Custom Machine Images

Custom AMIs (AWS) and GCP Images are built using HashiCorp Packer. Templates are in the `packer/` directory.

- **Source image:** Ubuntu 24.04 LTS
- **Builders:** `amazon-ebs` (AWS) and `googlecompute` (GCP) in a single template
- **Provisioning:** `scripts/setup.sh` installs all dependencies, deploys the app, and configures systemd
- **Image sharing:** AWS AMI shared with demo account, GCP image shared with demo project via IAM

### CI/CD Workflows
| Trigger | Workflow | Action |
|---|---|---|
| Pull request to `main` | `packer-validate.yml` | Validates Packer template formatting and syntax |
| Push to `main` | `packer-build.yml` | Runs integration tests, then builds and shares images |

## Security
- Passwords are hashed using BCrypt with auto-generated salts
- Email addresses are case-insensitive for uniqueness
- Never commit `.env` file or credentials to repository
- Use environment variables for all sensitive configuration
  
## Testing
The application includes 134 comprehensive integration tests covering:
- Positive test cases (creation, retrieval, update, authentication)
- Negative test cases (invalid inputs, auth errors, wrong methods)
- Edge cases (boundary values, concurrency, performance, security)

Tests use the same database configured via environment variables. Each test runs inside a transaction that is rolled back after completion, so no test data persists.

Run the full test suite:
```bash
python -m pytest -v
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
