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
|---|---|
| host | localhost |
| port | 54321 |
| Maintance DB | windnode_abw |
| User | windnode |
| Password | windnode |


### Import scenario data

Scenario data is contained in the database dump [windnode_db_200602.backup](https://next.rl-institut.de/s/Q3sLw7JZgjpXfbR).
Do the following steps to import the scenario data to your database

1. Download the above scenario data file
2. Import tables, data, and constraints by 
   ```
   pg_restore -U windnode -d windnode_abw -h localhost -p 54321 -W --no-owner --no-privileges --no-tablespace -1  <windnode_db_200602.backup
   ```

## Setup database connection config file

When you try to run `windnode_abw/run_scenario.py`, it will search for  the file `$HOME/.egoio/config.ini`.
More specifically, in the file `config.ini` it searches for a section `[windnode_abw]`.
It won't be found whe you run it for the first time. Subsequently, a command-line dialog opens that asks you for
database connection details.

When you use a local database, the section in the config looks like

```
[windnode_abw]
dialect = psycopg2
username = windnode
host = localhost
port = 54321
database = windnode_abw
```

## Run model with _status quo_ scenario

Execute `python windnode_abw/run_scenario.py`.
