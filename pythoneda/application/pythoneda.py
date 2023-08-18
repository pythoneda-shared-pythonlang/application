"""
pythoneda/application/pythoneda.py

This file defines PythonEDA.

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
import os
from pathlib import Path
import pkgutil
from pythoneda.application import HexagonalLayer
from pythoneda.banner import Banner
import sys
from typing import Callable, Dict, List
import warnings

class PythonEDA():
    """
    The glue that binds adapters from infrastructure layer to ports in the domain layer.

    Class name: PythonEDA

    Responsibilities:
        - It's executable, can run from the command line.
        - Delegates the processing of CLI arguments to CLI ports.
        - Dynamically discovers adapters (port implementations).
        - Acts as a primary port (adapter) to the domain.

    Collaborators:
        - CLI adapters.
        - Domain aggregates.
    """

    _singleton = None

    def __init__(self, banner=None, file=__file__):
        """
        Initializes the instance.
        :param banner: The project's banner.
        :type banner: pythoneda.banner.Banner
        :param file: The file where this specific instance is defined.
        :type file: str
        """
        super().__init__()
        self._primary_ports = []
        if banner:
            banner.print()
        self.fix_syspath(file)
        self.load_all_packages()
        self._domain_packages, self._domain_modules, self._infrastructure_packages, self._infrastructure_modules = self.load_pythoneda_packages()
        self._domain_ports = self.find_domain_ports(self._domain_modules)
        self.initialize()

    @property
    def domain_packages(self) -> List:
        """
        Retrieves the domain packages.
        :return: Such packages.
        :rtype: List
        """
        return self._domain_packages

    @property
    def domain_modules(self) -> List:
        """
        Retrieves the domain modules.
        :return: Such modules.
        :rtype: List
        """
        return self._domain_modules;

    @property
    def domain_ports(self) -> List:
        """
        Retrieves the port interfaces.
        :return: Such interfaces.
        :rtype: List
        """
        return self._domain_ports;

    @property
    def infrastructure_packages(self) -> List:
        """
        Retrieves the infrastructure packages.
        :return: Such packages.
        :rtype: List
        """
        return self._infrastructure_packages

    @property
    def infrastructure_modules(self) -> List:
        """
        Retrieves the infrastructure modules.
        :return: Such modules.
        :rtype: List
        """
        return self._infrastructure_modules;

    @property
    def primary_ports(self) -> List:
        """
        Retrieves the primary ports found.
        :return: Such ports.
        :rtype: List
        """
        return self._primary_ports

    def fix_syspath(self, file: str):
        """
        Fixes the sys.path collection to avoid duplicated entries for the specific project
        this (sub)class is defined.
        :param file: The file where this specific instance is defined.
        :type file: str
        """
        base_folder = str(Path().resolve())
        current_folder = Path(file).resolve().parent
        app_module = os.path.basename(current_folder)
        if os.path.isdir(Path(base_folder) / app_module) and str(current_folder) in sys.path:
            sys.path.remove(str(current_folder))
        path_to_remove = None
        for path in sys.path:
            if os.path.isdir(Path(path) / app_module):
                path_to_remove = path
                break
        if path_to_remove:
            sys.path.remove(str(path_to_remove))
        if base_folder not in sys.path:
            sys.path.append(base_folder)

    def from_pythoneda(self, pkg) -> bool:
        """
        Checks if given package is from PythonEDA.
        :param pkg: The package.
        :type pkg: module
        :return: True in such case.
        :rtype: bool
        """
        if pkg.__name__ == 'pythoneda':
            result = True
        elif pkg.__name__ == '' or pkg.__name__ == pkg.__package__:
            result = False
        else:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                try:
                    result = self.from_pythoneda(importlib.import_module(pkg.__package__))
                except ModuleNotFoundError as err:
                    import traceback
                    traceback.print_exc()
                    logging.getLogger(__name__).critical(f'Cannot import {pkg.__package__}: Missing dependency {err.name} !!')
                    logging.getLogger(__name__).critical(err)
        return result

    def load_all_packages(self):
        """
        Loads all packages.
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            for importer, pkg, ispkg in pkgutil.iter_modules():
                if pkg != 'tkinter':
                    if ispkg:
                        loader = importer.find_module(pkg)
                        try:
                            loader.load_module(pkg)
                        except Exception as err:
                            if pkg != "matplotlib_inline":
                                logging.getLogger(__name__).critical(f'Cannot import {pkg}: Missing dependency {err.name}')
                                logging.getLogger(__name__).critical(err)


    def custom_sort(self, item):
        split_item = item.split(".")
        return len(split_item), split_item

    def is_empty_namespace_folder(self, directory:str) -> bool:
        """
        Checks given folder is an empty namespace.
        :param directory: The folder to analyze.
        :type directory: str
        :return: True in such case.
        :rtype: bool
        """
        has_init = False
        has_other_py_files = False
        has_subfolders = False

        # List the contents of the directory
        for name in os.listdir(directory):
            path = os.path.join(directory, name)

            # Check if the file is __init__.py
            if os.path.isfile(path) and name == '__init__.py':
                has_init = True

            # Check if the file is not __init__.py
            if os.path.isfile(path) and name != '__init__.py' and name.endswith(".py"):
                has_other_py_files = True

            # Check if there are subdirectories
            if os.path.isdir(path):
                has_subfolders = True

        # Condition to make sure __init__.py is the only py file and there are subdirectories
        return has_init and has_subfolders and not has_other_py_files

    def get_path_of_packages_under_namespace(self, namespace:str) -> Dict:
        """
        Retrieves the paths of packages under given namespace.
        :param namespace: The namespace.
        :type namespace: str
        :return: A dictionary of package names and paths.
        :rtype: Dict[str, str]
        """
        all_sub_packages = {}

        for path in sys.path:
            init_file = Path(path) / "pythoneda" / Path("__init__.py")
            if os.path.exists(init_file):

            # walk through all files and directories in site-packages
                for root, dirs, _ in os.walk(path):

                    # only consider directories
                    for dir in dirs:

                        # construct the full path
                        full_path = os.path.join(root, dir)

                        # if this directory is a package
                        if os.path.isfile(os.path.join(full_path, '__init__.py')):

                            # get the package name
                            package_name = full_path[len(path)+1:].replace(os.sep, '.')

                            # if the package is a sub-package of the namespace
                            if package_name.startswith(namespace) and not all_sub_packages.get(package_name, None):
                                all_sub_packages[package_name] = full_path

        return all_sub_packages

    def load_pythoneda_packages(self) -> tuple:
        """
        Loads the PythonEDA-related packages.
        :return: A tuple consisting of (domain packages, domain modules, infrastructure packages, infrastructure modules).
        :rtype: tuple
        """

        domain_packages = []
        domain_modules = []
        infrastructure_packages = []
        infrastructure_modules = []
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            packages = self.get_path_of_packages_under_namespace("pythoneda")
            for package_name in packages:
                try:
                    package = __import__(package_name, fromlist=[''])
                    package_path = packages[package_name]
                    domain_package = bootstrap.is_domain_package(package)
                    infrastructure_package = bootstrap.is_infrastructure_package(package)
                    if domain_package:
                        if package_path not in domain_packages:
                            domain_packages.append(package_path)
                        submodules = bootstrap.import_submodules(package, True, HexagonalLayer.DOMAIN)
                        self.__class__.extend_missing_items(domain_modules, submodules.values())
                    if infrastructure_package:
                        if package_path not in infrastructure_packages:
                            infrastructure_packages.append(package_path)
                        submodules = bootstrap.import_submodules(package, True, HexagonalLayer.INFRASTRUCTURE)
                        self.__class__.extend_missing_items(infrastructure_modules, submodules.values())
                except Exception as err:
                    import traceback
                    traceback.print_exc()
                    logging.getLogger(__name__).critical(f'Cannot import {package_path}: Missing dependency {err} when trying to import {package_name}!!')
                    logging.getLogger(__name__).critical(err)

        return (domain_packages, domain_modules, infrastructure_packages, infrastructure_modules)

    def find_domain_ports(self, modules: List) -> List:
        """
        Retrieves the port interfaces.
        :param modules: The modules to process.
        :type modules: List
        :return: Such interfaces.
        :rtype: List
        """
        result = []
        from pythoneda.port import Port
        from pythoneda.primary_port import PrimaryPort
        for module in modules:
            if bootstrap.is_domain_module(module):
                interfaces = bootstrap.get_interfaces_of_module(Port, module, PrimaryPort)
                self.__class__.extend_missing_items(result, interfaces)
        return result

    @classmethod
    async def main(cls):
        """
        Runs the application from the command line.
        :param file: The file where this specific instance is defined.
        :type file: str
        """
        cls._singleton = cls()
        await cls.instance().accept_input()

    @classmethod
    def instance(cls):
        """
        Retrieves the singleton instance.
        :return: Such instance.
        :rtype: PythonEDA
        """
        return cls._singleton

    def initialize(self):
        """
        Initializes this instance.
        """
        mappings = {}
        if len(self.infrastructure_modules) == 0:
            logging.getLogger(__name__).critical(f'No infrastructure modules detected!')
        else:
            for port in self.domain_ports:
                implementations = bootstrap.get_adapters(port, self.infrastructure_modules)
                if len(implementations) == 0:
                    logging.getLogger(__name__).critical(f'No implementations found for {port} in {self.infrastructure_modules}')
                elif len(implementations) > 1:
                    logging.getLogger(__name__).critical(f'Several implementations found for {port}: {implementations}')
                    mappings.update({ port: implementations[0]() })
                else:
                    mappings.update({ port: implementations[0]() })
            from pythoneda.ports import Ports
            Ports.initialize(mappings)
            from pythoneda.primary_port import PrimaryPort
            self._primary_ports = bootstrap.get_adapters(PrimaryPort, self.infrastructure_modules)
            from pythoneda.event_listener import EventListener
            EventListener.find_listeners()
            from pythoneda.event_emitter import EventEmitter
            EventEmitter.register_receiver(self)

    @classmethod
    def delegate_priority(cls, primaryPort) -> int:
        """
        Delegates the priority information to given primary port.
        :param primaryPort: The primary port.
        :type primaryPort: pythoneda.Port
        :return: Such priority.
        :rtype: int
        """
        return primaryPort().priority()

    async def accept_input(self):
        """
        Notification the application has been launched from the CLI.
        """
        for primary_port in sorted(self.primary_ports, key=self.__class__.delegate_priority):
            port = primary_port()
            await port.accept(self)

    async def accept(self, event): # : Event) -> Event:
        """
        Accepts and processes an event, potentially generating others in response.
        :param event: The event to process.
        :type event: pythoneda.Event
        :return: The generated events in response.
        :rtype: List
        """
        result = []
        if event:
            firstEvents = []
            logging.getLogger(__name__).info(f'Accepting event {event}')
            from pythoneda.event_listener import EventListener
            EventListener.find_listeners()
            for listenerClass in EventListener.listeners_for(event.__class__):
                resultingEvents = await listenerClass.accept(event)
                if resultingEvents and len(resultingEvents) > 0:
                    self.__class__.extend_missing_items(firstEvents, resultingEvents)
            if len(firstEvents) > 0:
                self.__class__.extend_missing_items(result, firstEvents)
                for event in firstEvents:
                    self.__class__.extend_missing_items(result, await self.accept(event))
        return result

    async def emit(self, event):
        """
        Emits given event.
        :param event: The event to emit.
        :type event: pythoneda.Event
        """
        if event:
            event_emitter = Ports.instance().resolve(EventEmitter)
            await event_emitter.emit(event)

    async def accept_configure_logging(self, logConfig: Dict[str, bool]):
        """
        Receives information about the logging settings.
        :param logConfig: The logging config.
        :type logConfig: Dict[str, bool]
        """
        module_function = self.__class__.get_log_config()
        if module_function:
            module_function(logConfig["verbose"], logConfig["trace"], logConfig["quiet"])

    @classmethod
    def get_log_config(cls) -> Callable:
        """
        Retrieves the function to configure the logging system.
        :return: Such function.
        :rtype: Callable
        """
        result = None

        for module in cls.instance().infrastructure_modules:

            if module.__name__ == "_log_config":
#                spec.loader.exec_module(module)
                entry = {}
                configure_logging_function = getattr(module, "configure_logging", None)
                if callable(configure_logging_function):
                    result = configure_logging_function
                else:
                    print(f"Error in {module.__file__}: configure_logging")
        return result

    @classmethod
    def extend_missing_items(cls, first:List, second:List):
        """
        Adds the items of the second list into the first list, excluding those already included.
        :param first: The first list.
        :type first: List
        :param second: The second list.
        :type second: List
        """
        [first.append(item) for item in second if item not in first]

from pythoneda.application import bootstrap
import asyncio
import importlib
import importlib.util
import logging
import os
import sys

if __name__ == "__main__":

    asyncio.run(PythonEDA.main())
