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
from typing import Callable, Dict, List
import warnings

_domain_packages = {}
_infrastructure_packages = {}
_domain_modules = {}
_infrastructure_modules = {}

def _memoized(packagePath:str, type, cache:Dict, func:Callable) -> bool:
    """
    Retrieves whether given package matches a condition provided by `func`, using a cache to avoid redundant processing.
    :param packagePath: The path of the package to check.
    :type packagePath: str
    :param type: The aspect of the package to check.
    :type type: pythoneda.HexagonalLayer
    :param cache: The cache.
    :type cache: Dict.
    :param func: The function to call to process the package.
    :type func: Callable
    :return: True if so.
    :rtype: bool
    """
    result = cache.get(packagePath, None)
    if result is None:
        result = func(packagePath, type)
        cache[packagePath] = result
    return result

def is_domain_package(packagePath) -> bool:
    """
    Checks if given package is marked as domain package.
    :param packagePath: The package path.
    :type packagePath: str
    :return: True if so.
    :rtype: bool
    """
    return _memoized(packagePath, HexagonalLayer.DOMAIN, _domain_packages, is_of_type)

def is_infrastructure_package(packagePath:str) -> bool:
    """
    Checks if given package is marked as infrastructure package.
    :param packagePath: The package path.
    :type packagePath: str
    :return: True if so.
    :rtype: bool
    """
    return _memoized(packagePath, HexagonalLayer.INFRASTRUCTURE, _infrastructure_packages, is_of_type)

def get_folders_of_parent_packages(path) -> List:
    """
    Retrieves the folders of the parent packages.
    :param path: The initial path.
    :type path: str
    :return: The parent folders.
    :rtype: List
    """
    folder = path.rstrip("/")
    if not os.path.isdir(folder):
        folder = os.path.dirname(folder)

    current_path = folder
    while (Path(current_path) / "__init__.py").exists() and current_path != os.path.dirname(current_path):
        yield current_path
        current_path = os.path.dirname(current_path)

def is_of_type(path:str, type: HexagonalLayer) -> bool:
    """
    Checks if given path is marked as of given type.
    :param path: The package path.
    :type path: str
    :param type: The type of package.
    :type type: pythoneda.application.hexagonal_layer.HexagonalLayer
    :return: True if so.
    :rtype: bool
    """
    result = False
    for folder in get_folders_of_parent_packages(path):
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
    return _memoized(module.__file__, HexagonalLayer.DOMAIN, _domain_modules, is_of_type)

def is_infrastructure_module(module) -> bool:
    """
    Checks if given module is marked as infrastructure module.
    :param module: The module.
    :type module: builtins.module
    :return: True if so.
    :rtype: bool
    """
    return _memoized(module.__file__, HexagonalLayer.INFRASTRUCTURE, _domain_modules, is_of_type)

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
            logging.getLogger(__name__).error(f'Error importing {module}: {err}')

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

    if type is None or is_of_type(package.__path__[0], type):
        for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
            full_name = package.__name__ + '.' + name
            try:

                results[full_name] = __import__(full_name, fromlist=[''])

                if recursive and is_pkg:
                    child_package = __import__(full_name, fromlist=[''])
                    results.update(import_submodules(child_package, recursive)) # type is not considered for descendants.
            except ImportError as err:
                if not ".grpc." in full_name and not "logging." in full_name:
                    logging.getLogger(__name__).error(f'Error importing {full_name}: {err} while loading {package.__path__}')
    return results
