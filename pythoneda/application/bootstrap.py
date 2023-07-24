"""
pythoneda/application/bootstrap.py

This file performs the bootstrapping af PythonEDA applications.

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
import importlib.util
import inspect
import logging
import os
from pathlib import Path
import pkgutil
import sys
from typing import Dict, List
import warnings

def is_domain_package(package) -> bool:
    """
    Checks if given package is marked as domain package.
    :param package: The package.
    :type package: Package
    :return: True if so.
    :rtype: bool
    """
    return is_package_of_type(package, "domain")

def is_infrastructure_package(package) -> bool:
    """
    Checks if given package is marked as infrastructure package.
    :param package: The package.
    :type package: Package
    :return: True if so.
    :rtype: bool
    """
    return is_package_of_type(package, "infrastructure")

def is_package_of_type(package, type: str) -> bool:
    """
    Checks if given package is marked as of given type.
    :param package: The package.
    :type package: Package
    :param type: The type of package.
    :type type: str
    :return: True if so.
    :rtype: bool
    """
    package_path = Path(package.__path__[0])
    return (package_path / f".pythoneda-{type}").exists()

def get_interfaces_in_module(iface, module):
    """
    Retrieves the interfaces extending given one in a module.
    :param iface: The parent interface.
    :type iface: Object
    :param module: The module.
    :type module: Module
    :return: The list of intefaces in given module.
    :rtype: List
    """
    matches = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=DeprecationWarning)
            for class_name, cls in inspect.getmembers(module, inspect.isclass):
                if (issubclass(cls, iface) and
                    cls != iface):
                    matches.append(cls)
    except ImportError:
        pass
    return matches

def get_adapters(interface, modules: List):
    """
    Retrieves the implementations for given interface.
    :param interface: The interface.
    :type interface: Object
    :param modules: The modules to inspect.
    :type modules: List
    :return: The list of implementations.
    :rtype: List
    """
    implementations = []

    import abc
    for module in modules:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', category=DeprecationWarning)
                for class_name, cls in inspect.getmembers(module, inspect.isclass):
                    if (inspect.isclass(cls)) and (issubclass(cls, interface)) and (cls != interface) and (abc.ABC not in cls.__bases__):
                        implementations.append(cls)
        except ImportError as err:
            print(f'Error importing {module}: {err}')

    return implementations


def import_submodules(package, recursive=True):
    """
    Imports all submodules of a module, recursively, including subpackages.
    :param package: package (name or actual module)
    :type package: str | module
    :rtype: dict[str, types.ModuleType]
    """
    if isinstance(package, str):
        package = __import__(package, fromlist=[''])

    results = {}

    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + '.' + name

        results[full_name] = __import__(full_name, fromlist=[''])

        if recursive and is_pkg:
            results.update(import_submodules(full_name))

    return results
