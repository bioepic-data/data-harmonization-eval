"""Scoring of agent fold outputs against the BERDL lakehouse reference.

The eval harness (``src/folds``) builds answer-free fold environments and audits
the agent run; it deliberately does no scoring. This package is the "separate
trusted process, outside the fold environment" the README defers to.

Entry point: :mod:`src.metrics.run_all`.
"""
