# vim: set fileencoding=utf-8
"""
pythoneda/shared/application/enable.py

This file defines the "enable" annotation, to enable specific infrastructure modules.

Copyright (C) 2023-today rydnr's pythoneda-shared-pythoneda/application

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
import importlib
from .pythoneda import PythonEDA


def enable(adapterCls):
    def decorator(cls):
        module = importlib.import_module(adapterCls.__module__)
        if module not in PythonEDA.enabled_infrastructure_modules:
            adapterCls.enable()
            PythonEDA.enabled_infrastructure_modules.append(module)
        return cls

    return decorator
