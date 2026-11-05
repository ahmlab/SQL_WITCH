"""Try the guard yourself: python -m try_it_yourself.try_sandbox

Type any query and see what the guard does with it. Reads come back as (columns, rows);
anything that writes (DELETE, DROP, ALTER, UPDATE...) or is not valid SQL is refused with
the in-game message instead of a traceback. An empty line quits.
"""

from magic.db import build_db
from magic.guard import run_query, Miscast

conn = build_db()
# Try: "SELECT name, mp_cost FROM spells LIMIT 4", then try to break it: "DROP TABLE spells"
while True:
    sql = input("Write here: ").strip()
    if not sql:
        break
    try:
        print(run_query(conn, sql))
    except Miscast as miscast:             # the guard said no: show its message
        print(miscast)
