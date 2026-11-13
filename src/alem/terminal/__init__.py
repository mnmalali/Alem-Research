"""Small, dependency-free terminal presentation helpers for Alem."""

from .dashboard import render_dashboard
from .mascot import PALETTE, print_owl, render_ansi

__all__ = ["PALETTE", "print_owl", "render_ansi", "render_dashboard"]
