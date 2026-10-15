# MOTOR_ASSISTANT

## Local database

By default, the app uses the local `db.sqlite3` database. Start it from the
project folder with:

```powershell
python manage.py runserver
```

MySQL can be enabled with `USE_MYSQL=1`, but the project's Django 6.0 setup
requires MariaDB 10.11 or later.
