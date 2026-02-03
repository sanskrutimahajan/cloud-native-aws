# webapp

Cloud-native web application for CSYE6225.

## Prerequisites

- Python 3.x
- PostgreSQL installed and running
- pip (Python package manager)
- Git

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

Create a PostgreSQL database and a user for the application.

### 5. Configure environment variables

Create a `.env` file in the project root with your database and application configuration. Do not commit this file to version control.

Required environment variables:
- `DATABASE_HOST` - Database host
- `DATABASE_PORT` - Database port
- `DATABASE_NAME` - Database name
- `DATABASE_USER` - Database user
- `DATABASE_PASSWORD` - Database password
- `APP_HOST` - Application host
- `APP_PORT` - Application port
- `ENVIRONMENT` - Application environment (e.g., development, production)

### 6. Run the application

```bash
python run.py
```

The application will start on the host and port specified in your `.env` file.

## Testing

```bash
pytest
```
