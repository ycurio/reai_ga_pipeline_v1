# dbt Postgres sample

This folder contains a minimal dbt project for Postgres.

## Setup

1. Activate your project virtualenv:

```powershell
.\.venv\Scripts\Activate.ps1
```

2. Set your Postgres connection values:

```powershell
$env:DBT_HOST = 'localhost'
$env:DBT_USER = 'your_user'
$env:DBT_PASSWORD = 'your_password'
$env:DBT_DBNAME = 'your_database'
$env:DBT_SCHEMA = 'public'
```

3. Run dbt debug with the local profile file:

```powershell
dbt debug --profiles-dir .
```

## Run models

Run all models:

```powershell
dbt run --profiles-dir .
```

Run selected models:

```powershell
dbt run --models customers orders --profiles-dir .
```

Run one model plus its dependencies:

```powershell
dbt run --models +customer_orders --profiles-dir .
```

Run a model and its parents only:

```powershell
dbt run --models customer_orders+
```
