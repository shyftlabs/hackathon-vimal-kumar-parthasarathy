"""Scoring engines — pure functions over the mock fleet dataset.

Each engine reads from backend.data.seed_data and returns plain dicts (or
lists of dicts) with camelCase keys matching frontend/src/types/fleet.ts.
No side effects, no external calls. Return None on invalid input.
"""
