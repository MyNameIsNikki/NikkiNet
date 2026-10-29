#!/usr/bin/env python3
"""Apply the NikkiNet cyberpunk look to a sing-box-for-android checkout.

Called from mobile/brand.py, which runs in CI after libbox.aar is built and
before Gradle assembles the APK.  Every patch is checked so a silent upstream
rename cannot leave the app with the stock pink theme.
"""
import os
import re

BG = "0xFF05060D"
PANEL = "0xFF0B0F1A"
PANEL2 = "0xFF121A2B"
TEXT = "0xFFE8EEFC"
MUTED = "0xFF8FA2C7"
CYAN = "0xFF00F0FF"
CYAN2 = "0xFF5FFCFF"
MAGENTA = "0xFFFF2BD6"
VIOLET = "0xFF8A2BE2"
YELLOW = "0xFFF7FF3C"
OK = "0xFF39FF88"
ERR = "0xFFFF3860"
WARN = "0xFFFFCC00"

COLOR_KT = """package io.nekohasekai.sfa.compose.theme

import androidx.compose.ui.graphics.Color

// NikkiNet cyberpunk palette
val SingBoxPrimary = Color(%(cyan)s)
val SingBoxPrimaryDark = Color(0xFF00A6B2)
val SingBoxPrimaryLight = Color(%(cyan2)s)

val ServiceRunning = Color(%(ok)s)
val ServiceStopped = Color(0xFF6B7FA3)
val ServiceError = Color(%(err)s)

val LogRed = Color(%(err)s)
val LogGreen = Color(%(ok)s)
val LogYellow = Color(%(yellow)s)
val LogBlue = Color(%(cyan)s)
val LogPurple = Color(%(magenta)s)
val LogRedLight = Color(0xFFFF6B9A)
val LogBlueLight = Color(%(cyan2)s)
val LogWhite = Color(%(text)s)

val SeedColor = Color(%(cyan)s)

val SuccessGreen = Color(%(ok)s)
val WarningOrange = Color(%(warn)s)
val ErrorRed = Color(%(err)s)
val InfoBlue = Color(%(cyan)s)

// NikkiNet surfaces
val NikkiBg = Color(%(bg)s)
val NikkiPanel = Color(%(panel)s)
val NikkiPanel2 = Color(%(panel2)s)
val NikkiText = Color(%(text)s)
val NikkiMuted = Color(%(muted)s)
val NikkiMagenta = Color(%(magenta)s)
val NikkiViolet = Color(%(violet)s)
val NikkiYellow = Color(%(yellow)s)
""" % {
    "bg": BG,
    "panel": PANEL,
    "panel2": PANEL2,
    "text": TEXT,
    "muted": MUTED,
    "cyan": CYAN,
    "cyan2": CYAN2,
    "magenta": MAGENTA,
    "violet": VIOLET,
    "yellow": YELLOW,
    "ok": OK,
    "err": ERR,
    "warn": WARN,
}

SHAPE_KT = """package io.nekohasekai.sfa.compose.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

val Shapes =
    Shapes(
        extraSmall = RoundedCornerShape(2.dp),
        small = RoundedCornerShape(4.dp),
        medium = RoundedCornerShape(6.dp),
        large = RoundedCornerShape(8.dp),
        extraLarge = RoundedCornerShape(12.dp),
    )
"""

DARK_SCHEME = """private val DarkColorScheme =
    darkColorScheme(
        primary = SingBoxPrimary,
        onPrimary = NikkiBg,
        primaryContainer = NikkiPanel2,
        onPrimaryContainer = NikkiText,
        secondary = NikkiMagenta,
        onSecondary = NikkiBg,
        secondaryContainer = NikkiPanel2,
        onSecondaryContainer = NikkiText,
        tertiary = NikkiViolet,
        onTertiary = NikkiText,
        tertiaryContainer = NikkiPanel2,
        onTertiaryContainer = NikkiText,
        background = NikkiBg,
        onBackground = NikkiText,
        surface = NikkiPanel,
        onSurface = NikkiText,
        surfaceVariant = NikkiPanel2,
        onSurfaceVariant = NikkiMuted,
        error = ErrorRed,
        onError = NikkiBg,
        outline = NikkiMuted,
        scrim = NikkiBg,
    )"""

FOREGROUND = """<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="1024"
    android:viewportHeight="1024">
    <path
        android:pathData="M300,270 h130 v484 h-130 Z"
        android:fillColor="#00F0FF" />
    <path
        android:pathData="M594,270 h130 v484 h-130 Z"
        android:fillColor="#00F0FF" />
    <path
        android:pathData="M365,270 h145 L659,754 h-145 Z"
        android:fillColor="#FF2BD6" />
    <path
        android:pathData="M300,270 h130 v12 h-130 Z"
        android:fillColor="#5FFCFF" />
    <path
        android:pathData="M594,742 h130 v12 h-130 Z"
        android:fillColor="#5FFCFF" />
</vector>
"""

MONOCHROME = """<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp"
    android:height="108dp"
    android:viewportWidth="1024"
    android:viewportHeight="1024">
    <path
        android:pathData="M300,270 h130 v484 h-130 Z M594,270 h130 v484 h-130 Z M365,270 h145 L659,754 h-145 Z"
        android:fillColor="#FFFFFF"
        android:fillType="evenOdd" />
</vector>
"""

BACKGROUND_XML = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">#05060D</color>
</resources>
"""


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _need(path, text, needle):
    if needle not in text:
        raise SystemExit("theme patch: expected %r in %s" % (needle, path))


def apply(app_root):
    """Patch an Android app directory in place.  Raises on unknown layouts."""
    java = os.path.join(app_root, "src", "main", "java", "io", "nekohasekai", "sfa", "compose", "theme")
    res = os.path.join(app_root, "src", "main", "res")

    theme_path = os.path.join(java, "Theme.kt")
    theme = _read(theme_path)
    _need(theme_path, theme, "darkTheme: Boolean = isSystemInDarkTheme()")
    _need(theme_path, theme, "dynamicColor: Boolean = true")
    theme = theme.replace("darkTheme: Boolean = isSystemInDarkTheme()", "darkTheme: Boolean = true")
    theme = theme.replace("dynamicColor: Boolean = true", "dynamicColor: Boolean = false")
    theme = re.sub(r"private val DarkColorScheme =.*?\n    \)\n", DARK_SCHEME + "\n", theme, count=1, flags=re.S)
    theme = re.sub(r"private val LightColorScheme =.*?\n    \)\n", "private val LightColorScheme = DarkColorScheme\n", theme, count=1, flags=re.S)
    _need(theme_path, theme, "@Composable\nfun Theme(")
    _write(theme_path, theme)

    _write(os.path.join(java, "Color.kt"), COLOR_KT)
    _write(os.path.join(java, "Shape.kt"), SHAPE_KT)

    type_path = os.path.join(java, "Type.kt")
    typography = _read(type_path)
    if "FontFamily.Default" not in typography:
        raise SystemExit("theme patch: FontFamily.Default not found in %s" % type_path)
    _write(type_path, typography.replace("FontFamily.Default", "FontFamily.Monospace"))

    _write(os.path.join(res, "drawable", "ic_launcher_foreground.xml"), FOREGROUND)
    _write(os.path.join(res, "drawable", "ic_launcher_monochrome.xml"), MONOCHROME)
    _write(os.path.join(res, "values", "ic_launcher_background.xml"), BACKGROUND_XML)

    print("applied NikkiNet cyberpunk theme")
