"""The Spellbook: Scrolls, saved queries that are real SQL views (plan §4.4).

A query cast successfully often enough may be saved as CREATE VIEW scroll_<name>; casting the
Scroll is SELECT * FROM scroll_<name>, through the normal pipeline.

Must not: Never imports pygame. Never bypasses guard.inspect or cast.resolve.

STATUS: created (prompt 01); built in prompt 02.
"""
