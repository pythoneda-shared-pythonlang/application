# vim: set fileencoding=utf-8
"""
pythoneda/shared/application/enable.py

This file defines the "enable" annotation, to enable specific infrastructure modules.

Copyright (C) 2023-today rydnr's pythoneda-shared-pythonlang/application

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
import inspect
from .pythoneda import PythonEDA


def enable(adapterClsOrInstance):
    def decorator(cls):
        if inspect.isclass(adapterClsOrInstance):
            adapterCls = adapterClsOrInstance
            module = importlib.import_module(adapterCls.__module__)
            if module not in PythonEDA.enabled_infrastructure_modules:
                adapterCls.enable()
                PythonEDA.enabled_infrastructure_modules.append(module)
        else:
            adapterInstance = adapterClsOrInstance
            PythonEDA.enabled_infrastructure_adapters.append(adapterInstance)

        return cls

    return decorator


# vim: syntax=python ts=4 sw=4 sts=4 tw=79 sr et
# Local Variables:
# mode: python
# python-indent-offset: 4
# tab-width: 4
# indent-tabs-mode: nil
# fill-column: 79
# End:
