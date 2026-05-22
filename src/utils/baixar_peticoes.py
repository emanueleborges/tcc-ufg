#!/usr/bin/env python3
"""Compatibilidade: executa o baixador separado em webscrap.py."""

from webscrap import run


if __name__ == "__main__":
    raise SystemExit(run())
