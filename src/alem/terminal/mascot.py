"""Alem's purple pixel-art owl and safe terminal colour detection.

The renderer intentionally has no terminal-library dependency.  It keeps ANSI
decisions at the output boundary so JSON and redirected output stay clean.
"""

from __future__ import annotations

import ctypes
import os
import sys
from collections.abc import Mapping
from typing import TextIO

OWL = (
    "..PP........PP..",
    "..PPP......PPP..",
    "..PPPPPPPPPPPP..",
    "..PDDDPPPPDDDP..",
    "..PLLLPPPPLLLP..",
    "..PLKKPPPPKKLP..",
    "..PLKKPAAPKKLP..",
    "..PLLLPAAPLLLP..",
    "DDPPPPPPPPPPPPDD",
    "DDPPLPLPPLPLPPDD",
    "DDPPPLPPPPLPPPDD",
    "DDPPLPLPPLPLPPDD",
    ".DPPPPPPPPPPPPD.",
    "..PPPPPPPPPPPP..",
    "....AA....AA....",
    "...AAA....AAA...",
)

PALETTE: Mapping[str, tuple[int, int, int]] = {
    "P": (139, 92, 246),  # alem-purple       #8B5CF6
    "D": (91, 33, 182),  # alem-deep-purple  #5B21B6
    "L": (221, 214, 254),  # alem-lavender     #DDD6FE
    "K": (26, 16, 51),  # alem-ink          #1A1033
    "A": (251, 191, 36),  # alem-amber        #FBBF24
}

ANSI_RESET = "\x1b[0m"


def _pixel(x: int, y: int) -> tuple[int, int, int] | None:
    if 0 <= y < len(OWL) and 0 <= x < len(OWL[0]):
        return PALETTE.get(OWL[y][x])
    return None


def _isatty(stream: object) -> bool:
    value = getattr(stream, "isatty", None)
    try:
        return bool(value()) if callable(value) else False
    except OSError:
        return False


def _windows_vt_supported(stream: TextIO) -> bool:
    """Best-effort Windows VT check; failures simply select plain output."""

    if os.name != "nt":
        return True
    if not _isatty(stream):
        return False
    try:
        handle = getattr(stream, "buffer", stream).fileno()
        kernel32 = ctypes.windll.kernel32
        mode = ctypes.c_uint()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        enable_vt = 0x0004
        if not (mode.value & enable_vt):
            kernel32.SetConsoleMode(handle, mode.value | enable_vt)
        return True
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def supports_unicode(stream: TextIO = sys.stdout) -> bool:
    """Return whether the stream can encode the half-block glyphs."""

    encoding = getattr(stream, "encoding", None) or "utf-8"
    try:
        "▀▄█".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def should_use_color(
    stream: TextIO = sys.stdout,
    *,
    force: bool = False,
    no_color: bool = False,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Decide if ANSI colour is safe for ``stream``.

    ``force`` is intentionally explicit and wins over ``NO_COLOR`` for callers
    that own the output contract.  Normal CLI calls pass ``no_color`` for the
    user-facing ``--no-color`` switch.
    """

    env = os.environ if environ is None else environ
    if no_color:
        return False
    if not force and "NO_COLOR" in env:
        return False
    if not force and env.get("TERM", "").lower() == "dumb":
        return False
    if not force and not _isatty(stream):
        return False
    return _windows_vt_supported(stream)


def render_ansi(color: bool = True, *, unicode: bool = True) -> str:
    """Return the 16x16 owl as eight terminal rows.

    ``unicode=False`` uses ASCII ``#`` cells, which is safe for legacy Windows
    code pages and file-like objects without an encoding attribute.
    """

    full = "█"
    top_only = "▀"
    bottom_only = "▄"
    if not unicode:
        full = top_only = bottom_only = "#"

    lines: list[str] = []
    for y in range(0, len(OWL), 2):
        out: list[str] = []
        for x in range(len(OWL[0])):
            top, bottom = _pixel(x, y), _pixel(x, y + 1)
            if top and bottom:
                if color:
                    out.append(
                        f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m"
                        f"\x1b[48;2;{bottom[0]};{bottom[1]};{bottom[2]}m"
                        f"{top_only}{ANSI_RESET}"
                    )
                else:
                    out.append(full)
            elif top:
                if color:
                    out.append(f"\x1b[38;2;{top[0]};{top[1]};{top[2]}m{top_only}{ANSI_RESET}")
                else:
                    out.append(top_only)
            elif bottom:
                if color:
                    out.append(
                        f"\x1b[38;2;{bottom[0]};{bottom[1]};{bottom[2]}m{bottom_only}{ANSI_RESET}"
                    )
                else:
                    out.append(bottom_only)
            else:
                out.append(" ")
        lines.append("".join(out))
    return "\n".join(lines)


def print_owl(
    tagline: str | None = None,
    indent: int = 2,
    file: TextIO | None = None,
    *,
    color: bool | None = None,
    force_color: bool = False,
    no_color: bool = False,
) -> None:
    """Print the owl, safely handling TTYs, redirects, and narrow encodings."""

    output = file or sys.stdout
    use_color = (
        should_use_color(output, force=force_color, no_color=no_color) if color is None else color
    )
    use_unicode = supports_unicode(output)
    pad = " " * max(0, indent)
    text = "\n".join(
        pad + line for line in render_ansi(use_color, unicode=use_unicode).splitlines()
    )
    print(text, file=output)
    if tagline:
        print(f"{pad}{tagline}", file=output)


if __name__ == "__main__":
    print_owl("ALEM RESEARCH  ·  Research deeper.")
