"""The world after each query: snapshots, Rewind, the integrity check and reactions (plan §4.1).

Before a player query it snapshots the battle database; after any query it classifies the world
(intact, altered, damaged, broken) and finds the reactions that apply.

Must not: Never imports pygame. Never decides damage: cast.resolve does.

STATUS: created (prompt 01); built in prompt 02.
"""
