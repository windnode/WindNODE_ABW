# WindNODE_ABW
Simulation der Region Anhalt-Bitterfeld-Wittenberg im Projekt WindNODE

## Installation

Clone and install via `pip install -e` (a virtualenv is recommended).

**Notice:** The recent package **psycopg2-binary** in setup.py conflicts with the
**psycopg2** required by **egoio**. If the install breaks, use the following
temporary workaround:

Install requirements manually in your venv, **egoio** should be the last.
Install it without dependencies by using `pip install --no-dependencies
egoio`.

### Setup postgres database with docker (optional)

**Note** You don't have to necessarily use docker to create a Postgres database. Using a native installtion works as well

Inside the repo's root directory (where docker-compose.yml lives) execute

```
docker-compose up -d --build
```

Afterwards you can access the database via

| Field | Value |
| host | localhost |
| port | 5432 |
| Maintance DB | windnode_abw |
| User | windnode |
| Password | windnode |


