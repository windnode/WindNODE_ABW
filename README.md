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


## Setup database connection config file

When you try to run `windnode_abw/scenarios/run_scenario.py`, it will search for 
the file `$HOME/.egoio/config.ini`. More specifically, in the file `config.ini` 
it searches for a section `[windnode_abw]`. It won't be found whe you run it for
the first time. Subsequently, a command-line dialog opens that asks you for database
connection details.

When you use a local database, the section in the config looks like

```
[windnode_abw]
dialect = psycopg2
username = windnode
host = localhost
port = 5432
database = windnode_abw
```