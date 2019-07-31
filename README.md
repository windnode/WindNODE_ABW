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
