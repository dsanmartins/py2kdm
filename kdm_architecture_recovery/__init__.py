"""
Architecture recovery package for py2kdm.

This package adds a semi-automatic architecture recovery layer over the
intermediate JSON model produced by python_kdm_extractor.

The first implementation focuses on self-adaptive systems and MAPE-K recovery.
It is intentionally conservative: MAPE-K recovery is activated only when the
project passes an autonomic applicability gate.
"""
