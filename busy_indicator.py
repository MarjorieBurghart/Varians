# -*- coding: utf-8 -*-
"""Indicateur d'attente discret : une lueur qui parcourt un petit cercle.

Affiché dans la barre d'état, juste avant « RNG », tant qu'une validation
RELAX NG est en cours dans le processus séparé (voir validation_worker). Il
n'est animé que parce que la fenêtre n'est plus bloquée pendant ce temps.
Couleurs prises dans la palette de l'interface.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

# Un tour par seconde : 20 pas de 18° toutes les 50 ms.
_STEP_DEGREES = 18
_INTERVAL_MSEC = 50
# Traînée de la lueur : rang du point derrière la tête → opacité.
_TRAIL = (1.0, 0.55, 0.3, 0.15)


class BusyIndicator(QWidget):
    """Petit cercle animé, masqué tant qu'il n'est pas démarré."""

    def __init__(self, parent=None, size=14):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_INTERVAL_MSEC)
        self._timer.timeout.connect(self._advance)
        self.hide()

    def start(self):
        if not self._timer.isActive():
            self._timer.start()
        self.show()

    def stop(self):
        self._timer.stop()
        self.hide()

    def is_running(self):
        return self._timer.isActive()

    def _advance(self):
        self.angle = (self.angle + _STEP_DEGREES) % 360
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = min(self.width(), self.height()) / 2 - 2.5
        center = QPointF(self.width() / 2, self.height() / 2)
        track = self.palette().color(QPalette.ColorRole.Mid)
        painter.setPen(QPen(track, 1.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)
        glow = self.palette().color(QPalette.ColorRole.Highlight)
        painter.setPen(Qt.PenStyle.NoPen)
        for rank, opacity in enumerate(_TRAIL):
            angle = math.radians(self.angle - rank * _STEP_DEGREES)
            dot = QColor(glow)
            dot.setAlphaF(opacity)
            painter.setBrush(dot)
            size = 2.4 - rank * 0.35
            point = QPointF(center.x() + radius * math.cos(angle), center.y() + radius * math.sin(angle))
            painter.drawEllipse(QRectF(point.x() - size, point.y() - size, 2 * size, 2 * size))
