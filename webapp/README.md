# webapp

Cloud-native web application for CSYE 6225. Built with FastAPI and PostgreSQL, it provides RESTful APIs for health monitoring, user management, course catalog management, and syllabus file storage using AWS S3. The application is designed to run on AWS EC2 with an RDS PostgreSQL database and S3 for file storage.

## Prerequisites

**Local development:**
- Python 3.10 or higher
- PostgreSQL 16 (local development and CI only — production uses AWS RDS)
- pip (Python package manager)
- Git

**Cloud deployment (EC2):**
- AWS EC2 instance launched from a Packer-built AMI
- AWS RDS PostgreSQL instance (private subnet)
- AWS S3 bucket (provisioned by Terraform)
- IAM role attached to EC2 instance (no hardcoded credentials)

## Frameworks and Libraries

| Dependency | Version | Purpose |
|---|---|---|
| FastAPI | 0.104.1 | Web framework |
| Uvicorn | 0.24.0 | ASGI server |
| SQLAlchemy | 2.0.23 | ORM / database toolkit |
| psycopg2-binary | 2.9.9 | PostgreSQL driver |
| bcrypt | 4.1.1 | Password hashing |
| Pydantic | 2.5.0 | Data validation (with email support) |
| python-dotenv | 1.0.0 | Environment variable loading |
| boto3 | 1.35.0 | AWS SDK — S3 file upload/delete |
| python-multipart | 0.0.6 | Multipart form data (file uploads) |
| pytest | 7.4.3 | Test framework |
| httpx | 0.25.2 | HTTP test client |
| pytest-cov | 4.1.0 | Test coverage reporting |

All dependencies are listed in `requirements.txt`.

## Environment Variables

The application reads all configuration from environment variables (loaded from `.env` in development, injected via EC2 user data in production).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_HOST` | `localhost` | Database hostname or RDS endpoint |
| `DATABASE_PORT` | `5432` | Database port |
| `DATABASE_NAME` | `webapp_db` | Database name |
| `DATABASE_USER` | `webapp_user` | Database username |
| `DATABASE_PASSWORD` | _(empty)_ | Database password |
| `APP_HOST` | `0.0.0.0` | Application bind host |
| `APP_PORT` | `8080` | Application bind port |
| `S3_BUCKET_NAME` | _(empty)_ | S3 bucket name for syllabus uploads |

> **Never commit `.env` or any file containing credentials to version control.**

## Automated Setup (EC2 / Ubuntu 24.04 LTS)

The `scripts/setup.sh` script is used by Packer to bake the application into an AMI. It does **not** install a local database — the application connects to an RDS instance whose credentials are injected via EC2 user data at launch time.

The script performs:
1. Updates and upgrades system packages
2. Creates a dedicated Linux group and user (`csye6225`)
3. Deploys application files to `/opt/csye6225/`
4. Installs Python 3, pip, venv, and all dependencies
5. Sets file ownership and permissions
6. Creates a placeholder `.env` file (overwritten by EC2 user data at launch)
7. Creates and enables a systemd service (`csye6225.service`) to start on boot

EC2 user data (from Terraform) writes the following into `/opt/csye6225/.env` before the service starts:
```
DATABASE_HOST=<rds-endpoint>
DATABASE_PORT=5432
DATABASE_NAME=csye6225
DATABASE_USER=csye6225
DATABASE_PASSWORD=<password>
S3_BUCKET_NAME=<bucket-uuid>
```

## Manual Setup (Local Development)

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

### 4. Set up a local PostgreSQL database
```bash
createdb webapp_db
```

### 5. Configure environment variables
Create a `.env` file in the project root (this file is gitignored and must never be committed):
```
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=webapp_db
DATABASE_USER=<your-db-user>
DATABASE_PASSWORD=<your-db-password>
APP_HOST=0.0.0.0
APP_PORT=8080
S3_BUCKET_NAME=<your-s3-bucket-name>
```

### 6. Run the application
```bash
python run.py
```

The application starts at `http://localhost:8080` by default.

## API Endpoints

All authenticated endpoints require HTTP Basic Auth. Unauthenticated requests return `401 Unauthorized`.

### Health & Metadata
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/healthz` | None | Health check — verifies database connectivity |
| GET | `/v1/metadata` | None | Cloud instance metadata (auto-detects AWS/GCP) |

### User Management
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/v1/user` | None | Create a new user account |
| GET | `/v1/user/self` | Basic Auth | Retrieve authenticated user information |
| PUT | `/v1/user/self` | Basic Auth | Update first_name, last_name, or password |

### Course Catalog
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/v1/courses` | Basic Auth | List all courses (sorted by dept code + number) |
| POST | `/v1/courses` | Basic Auth | Create a new course |
| GET | `/v1/courses/{course_id}` | Basic Auth | Retrieve a course by ID |
| PUT | `/v1/courses/{course_id}` | Basic Auth | Update a course (title, credit_hours, classification, description, prerequisites) |
| DELETE | `/v1/courses/{course_id}` | Basic Auth | Delete a course (blocked if syllabus exists) |

### Syllabus Management
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/v1/courses/{course_id}/syllabus` | Basic Auth | Upload a syllabus file (multipart/form-data) |
| GET | `/v1/courses/{course_id}/syllabus` | Basic Auth | Retrieve syllabus S3 metadata |
| DELETE | `/v1/courses/{course_id}/syllabus` | Basic Auth | Delete syllabus from S3 and database |

### Course Validation Rules
| Field | Rule |
|---|---|
| `department_code` | 2–6 uppercase letters only (regex: `^[A-Z]{2,6}$`) |
| `number` | 1–6 characters |
| `title` | 1–255 characters |
| `credit_hours` | Integer between 1 and 8 (inclusive) |
| `classification` | Must be `core` or `elective` |
| `description` | Optional, max 2000 characters |
| `prerequisites` | Optional, max 512 characters |
| `department_code + number` | Must be unique across all courses |

### Syllabus S3 Key Format
To prevent name collisions when two courses upload files with the same name:
```
{course_id}/{uuid}/{original_file_name}
```
Example: `c3d4e5f6-.../a1b2c3d4-.../syllabus.pdf`

## Packer — Custom Machine Images

Custom AMIs (AWS) and GCP images are built using HashiCorp Packer. Templates are in the `packer/` directory.

- **Source image:** Ubuntu 24.04 LTS
- **Builders:** `amazon-ebs` (AWS) and `googlecompute` (GCP) in a single template
- **Provisioning:** `scripts/setup.sh` installs all dependencies, deploys the app, and configures systemd
- **Image sharing:** AWS AMI shared with demo account; GCP image shared with demo project via IAM
- **No local database in AMI:** The AMI does not include PostgreSQL — the app connects to RDS via credentials from EC2 user data

## CI/CD Workflows

| Trigger | Workflow | Action |
|---|---|---|
| Pull request to `main` | `ci.yml` | Runs full integration test suite against a local PostgreSQL instance |
| Pull request to `main` | `packer-validate.yml` | Validates Packer template formatting and syntax |
| PR merged into `main` | `packer-build.yml` | Runs integration tests, then builds and shares AMI/GCP images |

### CI Database
Integration tests in GitHub Actions use a local PostgreSQL 16 service container. S3 calls are mocked in the test suite using `unittest.mock.patch` — no real AWS credentials are needed in CI.

## Security
- Passwords are hashed using BCrypt with auto-generated salts
- Email addresses are case-insensitive for uniqueness checks
- No hardcoded credentials anywhere in the codebase
- All AWS access uses IAM roles via boto3 default credential chain (no access keys)
- `.env` file is gitignored and must never be committed
- `S3_BUCKET_NAME` and all database credentials are injected at runtime via EC2 user data

## Testing

The application includes **235 comprehensive integration tests** across 5 test files:

| File | Tests | Coverage |
|---|---|---|
| `test_healthz.py` | Health check endpoint |  200, 400, 405, 503, caching, concurrency |
| `test_metadata.py` | Metadata endpoint | AWS/GCP detection, 400, 405, 503 |
| `test_user.py` | User management | Create, retrieve, update, auth, edge cases |
| `test_courses.py` | Course CRUD | All endpoints, validation, business rules |
| `test_syllabus.py` | Syllabus management | Upload, retrieve, delete, S3 key uniqueness |

Tests use transactional isolation — each test runs inside a transaction that is rolled back after completion, so no test data persists between tests. S3 operations are mocked so tests run without AWS credentials.

### Run tests
```bash
# Full test suite
pytest -v

# With coverage report
pytest --cov=app --cov-report=term-missing

# Specific test files
pytest tests/test_healthz.py -v
pytest tests/test_user.py -v
pytest tests/test_courses.py -v
pytest tests/test_syllabus.py -v
```
