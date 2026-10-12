"""Golden fixtures: ``python -m scripts.golden.dump [--update]`` writes the
responses of ``scripts/golden/requests.json`` to ``tests/golden/responses/``;
``tests/api/test_golden.py`` diffs the live API against them. The Next.js app
reuses the same files as MSW/Vitest fixtures.
"""
