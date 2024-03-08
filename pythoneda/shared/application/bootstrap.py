# vim: set fileencoding=utf-8
"""
pythoneda/shared/application/bootstrap.py

This file performs the bootstrapping af PythonEDA applications.

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
import importlib.util
import inspect
import os
from pathlib import Path
import pkgutil
import sys
from typing import Callable, Dict, List
import warnings


class Bootstrap:
    """
    Provides logic required to bootstrapping PythonEDA applications.

    Class name: Bootstrap

    Responsibilities:
        - Helps bootstrapping PythonEDA applications.

    Collaborators:
        - None
    """

    _singleton = None
    _domain_packages = {}
    _infrastructure_packages = {}
    _domain_modules = {}
    _infrastructure_modules = {}

    @classmethod
    def instance(cls):
        """
        Retrieves the singleton instance.
        :return: Such instance.
        :rtype: pythoneda.shared.application.Bootstrap
        """
        if cls._singleton == None:
            cls._singleton = cls()
        return cls._singleton

    @staticmethod
    def _memoized(packagePath: str, type, cache: Dict, func: Callable) -> bool:
        """
        Retrieves whether given package matches a condition provided by `func`, using a cache to avoid redundant processing.
        :param packagePath: The path of the package to check.
        :type packagePath: str
        :param type: The aspect of the package to check.
        :type type: pythoneda.shared.artifact.HexagonalLayer
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

    def is_domain_package(self, packagePath) -> bool:
        """
        Checks if given package is marked as domain package.
        :param packagePath: The package path.
        :type packagePath: str
        :return: True if so.
        :rtype: bool
        """
        from pythoneda.shared.artifact import HexagonalLayer

        return self._memoized(
            packagePath,
            HexagonalLayer.DOMAIN,
            self.__class__._domain_packages,
            self.is_of_type,
        )

    def is_infrastructure_package(self, packagePath: str) -> bool:
        """
        Checks if given package is marked as infrastructure package.
        :param packagePath: The package path.
        :type packagePath: str
        :return: True if so.
        :rtype: bool
        """
        from pythoneda.shared.artifact import HexagonalLayer

        return self._memoized(
            packagePath,
            HexagonalLayer.INFRASTRUCTURE,
            self.__class__._infrastructure_packages,
            self.is_of_type,
        )

    def get_folders_of_parent_packages(self, path) -> List:
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
        while (
            Path(current_path) / "__init__.py"
        ).exists() and current_path != os.path.dirname(current_path):
            yield current_path
            current_path = os.path.dirname(current_path)

    def is_of_type(self, path: str, type) -> bool:  #: HexagonalLayer) -> bool:
        """
        Checks if given path is marked as of given type.
        :param path: The package path.
        :type path: str
        :param type: The type of package.
        :type type: pythoneda.shared.artifact.HexagonalLayer
        :return: True if so.
        :rtype: bool
        """
        result = False
        if (Path(os.path.dirname(path)) / f".pythoneda-{type.name.lower()}").exists():
            result = True
        else:
            from pythoneda.shared.artifact import HexagonalLayer

            if type == HexagonalLayer.DOMAIN and (
                (
                    Path(os.path.dirname(path))
                    / f".pythoneda-{HexagonalLayer.INFRASTRUCTURE.name.lower()}"
                ).exists()
                or (
                    Path(os.path.dirname(path))
                    / f".pythoneda-{HexagonalLayer.APPLICATION.name.lower()}"
                ).exists()
            ):
                result = False
            else:
                for folder in self.get_folders_of_parent_packages(path):
                    if (Path(folder) / f".pythoneda-{type.name.lower()}").exists():
                        result = True
                        break
                    elif (
                        type != HexagonalLayer.DOMAIN
                        and (
                            Path(os.path.dirname(path))
                            / f".pythoneda-{HexagonalLayer.DOMAIN.name.lower()}"
                        ).exists()
                    ):
                        result = False
                        break

        return result

    def is_domain_module(self, module) -> bool:
        """
        Checks if given module is marked as domain module.
        :param module: The module.
        :type module: builtins.module
        :return: True if so.
        :rtype: bool
        """
        from pythoneda.shared.artifact import HexagonalLayer

        return self._memoized(
            module.__file__,
            HexagonalLayer.DOMAIN,
            self.__class__._domain_modules,
            self.is_of_type,
        )

    def is_infrastructure_module(self, module) -> bool:
        """
        Checks if given module is marked as infrastructure module.
        :param module: The module.
        :type module: builtins.module
        :return: True if so.
        :rtype: bool
        """
        from pythoneda.shared.artifact import HexagonalLayer

        return self._memoized(
            module.__file__,
            HexagonalLayer.INFRASTRUCTURE,
            self.__class__._infrastructure_modules,
            self.is_of_type,
        )

    def get_interfaces_of_module(self, iface, module, excluding=None):
        """
        Retrieves the interfaces extending given one in a module.
        :param iface: The parent interface.
        :type iface: Object
        :param module: The module.
        :type module: builtins.module
        :param excluding: Do not take into account matches implementing this class.
        :type excluding: type
        :return: The list of interfaces of given module.
        :rtype: List
        """
        result = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            try:
                for class_name, self in inspect.getmembers(module, inspect.isclass):
                    if issubclass(self, iface) and self != iface:
                        if excluding and issubclass(self, excluding):
                            pass
                        else:
                            result.append(self)
            except ImportError:
                stderr.write(f"Cannot get members of {module}\n")
                pass
        return result

    def get_adapters(self, interface, modules: List):
        """
        Retrieves the implementations for given interface.
        :param interface: The interface.
        :type interface: Object
        :param modules: The modules to inspect.
        :type modules: List[builtins.module]
        :return: The list of implementations.
        :rtype: List
        """
        result = []

        import abc

        for module in modules:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", category=DeprecationWarning)
                    for class_name, inst in inspect.getmembers(module, inspect.isclass):
                        if (
                            (inspect.isclass(inst))
                            and (issubclass(inst, interface))
                            and (inst != interface)
                            and (abc.ABC not in inst.__bases__)
                            and not inst in result
                        ):
                            result.append(inst)
            except ImportError as err:
                Bootstrap.logger().error(f"Error importing {module}: {err}")

        return result

    def import_submodules(
        self, package, type, recursive=True
    ):  #: HexagonalLayer = None, recursive = True):
        """
        Imports all submodules of a module, recursively, including subpackages.
        :param package: package (name or actual module)
        :type package: builtins.module
        :param type: The type of submodules (domain or infrastructure)
        :type type: pythoneda.shared.artifact.HexagonalLayer
        :param recursive: Whether to recursively import submodules.
        :type recursive: bool
        :rtype: dict[str, types.ModuleType]
        """
        results = {}

        if type is None or self.is_of_type(package.__path__[0], type):
            for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
                full_name = package.__name__ + "." + name
                try:
                    results[full_name] = __import__(full_name, fromlist=[""])
                    if recursive and is_pkg:
                        child_package = __import__(full_name, fromlist=[""])
                        results.update(
                            self.import_submodules(child_package, None, recursive)
                        )  # type is not considered for descendants.
                except ImportError as err:
                    if (
                        not ".grpc." in full_name
                        and not ".logging." in full_name
                        and not ".git."
                    ):
                        Bootstrap.logger().error(
                            f"Error importing {full_name}: {err} while loading {package.__path__}"
                        )
        return results


# vim: syntax=python ts=4 sw=4 sts=4 tw=79 sr et
# Local Variables:
# mode: python
# python-indent-offset: 4
# tab-width: 4
# indent-tabs-mode: nil
# fill-column: 79
# End:
