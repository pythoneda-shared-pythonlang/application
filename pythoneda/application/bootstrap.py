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
from pythoneda.application.hexagonal_layer import HexagonalLayer
import sys
from typing import Dict, List
import warnings

def is_domain_package(package) -> bool:
    """
    Checks if given package is marked as domain package.
    :type package: builtins.module
    :type package: package
    :return: True if so.
    :rtype: bool
    """
    return is_package_of_type(package, HexagonalLayer.DOMAIN)

def is_infrastructure_package(package) -> bool:
    """
    Checks if given package is marked as infrastructure package.
    :param package: The package.
    :type package: builtins.module
    :return: True if so.
    :rtype: bool
    """
    return is_package_of_type(package, HexagonalLayer.INFRASTRUCTURE)

def get_folders_of_parent_packages(path) -> List:
    """
    Retrieves the folders of the parent packages.
    :param path: The initial path.
    :type path: str
    :return: The parent folders.
    :rtype: List
    """
    current_path = path
    while (Path(current_path) / "__init__.py").exists() and current_path != os.path.dirname(current_path):
        yield current_path
        current_path = os.path.dirname(current_path)

def is_package_of_type(package, type: HexagonalLayer) -> bool:
    """
    Checks if given package is marked as of given type.
    :param package: The package.
    :type package: builtins.module
    :param type: The type of package.
    :type type: pythoneda.application.hexagonal_layer.HexagonalLayer
    :return: True if so.
    :rtype: bool
    """
    result = False
    for folder in get_folders_of_parent_packages(package.__path__[0]):
        if (Path(folder) / f".pythoneda-{type.name.lower()}").exists():
            result = True
            break

    return result

def is_domain_module(module) -> bool:
    """
    Checks if given module is marked as domain module.
    :type module: builtins.module
    :type module: module
    :return: True if so.
    :rtype: bool
    """
    return is_module_of_type(module, HexagonalLayer.DOMAIN)

def is_infrastructure_module(module) -> bool:
    """
    Checks if given module is marked as infrastructure module.
    :param module: The module.
    :type module: builtins.module
    :return: True if so.
    :rtype: bool
    """
    return is_module_of_type(module, HexagonalLayer.INFRASTRUCTURE)

def is_module_of_type(module, type: HexagonalLayer) -> bool:
    """
    Checks if given module is marked as of given type.
    :param module: The module.
    :type module: builtins.module
    :param type: The type of module.
    :type type: pythoneda.application.hexagonal_layer.HexagonalLayer
    :return: True if so.
    :rtype: bool
    """
    result = False
    for folder in get_folders_of_parent_packages(os.path.dirname(module.__file__)):
        if (Path(folder) / f".pythoneda-{type.name.lower()}").exists():
            result = True
            break

    return result

def get_interfaces_of_module(iface, module, excluding=None):
    """
    Retrieves the interfaces extending given one in a module.
    :param iface: The parent interface.
    :type iface: Object
    :param module: The module.
    :type module: builtins.module
    :param excluding: Do not take into account matches implementing this class.
    :type excluding: type
    :return: The list of intefaces of given module.
    :rtype: List
    """
    result = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=DeprecationWarning)
        try:
            for class_name, cls in inspect.getmembers(module, inspect.isclass):
                if (issubclass(cls, iface) and
                    cls != iface):
                    if excluding and issubclass(cls, excluding):
                        pass
                    else:
                        result.append(cls)
        except ImportError:
            logging.getLogger(__name__).critical(f'Cannot get members of {module}')
            pass

    return result

def get_adapters(interface, modules: List):
    """
    Retrieves the implementations for given interface.
    :param interface: The interface.
    :type interface: Object
    :param modules: The modules to inspect.
    :type modules: List[builtins.module]
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
                    if (inspect.isclass(cls)) and (issubclass(cls, interface)) and (cls != interface) and (abc.ABC not in cls.__bases__) and not cls in implementations:
                        implementations.append(cls)
        except ImportError as err:
            print(f'Error importing {module}: {err}')

    return implementations


def import_submodules(package, recursive=True, type:HexagonalLayer=None):
    """
    Imports all submodules of a module, recursively, including subpackages.
    :param package: package (name or actual module)
    :type package: builtins.module
    :param type: The type of submodules (domain or infrastructure)
    :type type: pythoneda.application.hexagonal_layer.HexagonalLayer
    :param recursive: Whether to recursively import submodules.
    :type recursive: bool
    :rtype: dict[str, types.ModuleType]
    """
    results = {}

    if type is None or is_package_of_type(package, type):
        for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
            full_name = package.__name__ + '.' + name
            try:
                results[full_name] = __import__(full_name, fromlist=[''])

                if recursive and is_pkg:
                    child_package = __import__(full_name, fromlist=[''])
                    results.update(import_submodules(child_package, recursive)) # type is not considered for descendants.
            except ImportError as err:
                if not ".grpc." in full_name:
                    print(f'Error importing {full_name}: {err}')
    return results
