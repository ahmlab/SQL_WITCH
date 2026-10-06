from magic.db import build_db
from magic.guard import run_query, inspect, Miscast

conn = build_db()
# Try: "SELECT name, mp_cost FROM spells LIMIT 4"
print(run_query(conn, input()))