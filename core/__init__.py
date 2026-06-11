"""Blackridge platform core: normalization + metric enrichment.

Pure, DB-agnostic logic. `normalize` turns a raw NSE option-chain JSON into
per-strike snapshot rows; `enrich` turns those rows into one instrument-level
metrics row. Both target the schema in db/migrations/0001_init.sql.
"""
