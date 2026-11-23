"""Try the guard yourself: python -m try_it_yourself.try_sandbox

Type any query and see what the guard does with it. Since sandbox v2 the world is free:
reads come back as (columns, rows), writes (INSERT, DELETE, DROP, ALTER...) run and come back
as ([], []). Only what is unsafe for the program (ATTACH, VACUUM, random(), two statements
outside a BEGIN ... COMMIT block) or not valid SQL is refused, with the in-game message.
An empty line quits.
"""

from magic.db import build_db
from magic.guard import inspect, run_query, Miscast

conn = build_db()
# Try: "SELECT name, mp_cost FROM spells LIMIT 4", then "DELETE FROM items", then "ATTACH 'x.db' AS x"
while True:
    sql = input("Write here: ").strip()
    if not sql:
        break
    try:
        inspect(sql)                       # the guard reads it first, as in the game
        print(run_query(conn, sql))
    except Miscast as miscast:             # the guard said no: show its message
        print(miscast)
