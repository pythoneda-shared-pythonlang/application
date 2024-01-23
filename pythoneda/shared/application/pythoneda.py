# vim: set fileencoding=utf-8
"""
pythoneda/shared/application/pythoneda.py

This file defines PythonEDA.

Copyright (C) 2023-today rydnr's pythoneda-shared/application

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
from .bootstrap import Bootstrap

# from eventsourcing.application import Application
import importlib
import inspect
import logging
import os
from pathlib import Path
import pkgutil
from pythoneda.shared.artifact import HexagonalLayer
from pythoneda.shared.banner import Banner
from pythoneda.shared.infrastructure.cli import LoggingConfigCli
from pythoneda.shared.infrastructure.logging import LoggingAdapter
import sys
from typing import Callable, Dict, List
import warnings


class PythonEDA:
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

    _default_logging_configured = False
    _singleton = None
    _enabled_infrastructure_modules = []

    def __init__(self, banner=None, file=__file__):
        """
        Initializes the instance.
        :param banner: The project's banner.
        :type banner: pythoneda.shared.banner.Banner
        :param file: The file where this specific instance is defined.
        :type file: str
        """
        super().__init__()
        self._primary_ports = []
        self._banner = banner
        self.fix_syspath(file)
        self.sort_pythoneda_package_in_sys_path()
        self.load_all_packages()
        (
            self._domain_packages,
            self._domain_modules,
            self._infrastructure_packages,
        ) = self.load_pythoneda_packages()
        self._domain_ports = self.find_domain_ports(self._domain_modules)
        self._one_shot = False
        self.initialize()

    @classmethod
    @property
    def enabled_infrastructure_modules(cls) -> List:
        """
        Retrieves the enabled infrastructure modules.
        :return: Such list.
        :rtype: List
        """
        return cls._enabled_infrastructure_modules

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
        return self._domain_modules

    @property
    def domain_ports(self) -> List:
        """
        Retrieves the port interfaces.
        :return: Such interfaces.
        :rtype: List
        """
        return self._domain_ports

    @property
    def infrastructure_packages(self) -> List:
        """
        Retrieves the infrastructure packages.
        :return: Such packages.
        :rtype: List
        """
        return self._infrastructure_packages

    @property
    def primary_ports(self) -> List:
        """
        Retrieves the primary ports found.
        :return: Such ports.
        :rtype: List
        """
        return self._primary_ports

    @property
    def banner(self):
        """
        Retrieves the banner, if any.
        :return: The banner instance.
        :rtype: pythoneda.shared.banner.Banner
        """
        return self._banner

    @property
    def one_shot(self) -> bool:
        """
        Retrieves whether one-shot behaviour is specified.
        :return: Such flag.
        :rtype: bool
        """
        return self._one_shot

    @one_shot.setter
    def one_shot(self, value: bool):
        """
        Specifies whether one-shot behavior is active.
        :param value: Whether to activate such behavior.
        :type value: bool
        """
        self._one_shot = value

    def sort_pythoneda_package_in_sys_path(self):
        """
        Sorts sys.path so that the pythoneda package is provided by the actual root package.
        """
        root_module = self.find_actual_root_pythoneda_package_path()
        root = os.path.dirname(root_module)
        sys.path.remove(root)
        sys.path.insert(0, root)

    def fix_syspath(self, file: str):
        """
        Fixes the sys.path collection to avoid duplicated entries for the specific project
        this (sub)class is defined.
        :param file: The file where this specific instance is defined.
        :type file: str
        """
        paths_to_add = []
        paths_to_remove = []

        for path in sys.path:
            root_path = self.find_root_of(path)
            if root_path != path:
                paths_to_remove.append(path)
                paths_to_add.append(root_path)

        for path_to_remove in paths_to_remove:
            sys.path.remove(os.path.abspath(path_to_remove))

        for path_to_add in paths_to_add:
            sys.path.append(os.path.abspath(path_to_add))

    def from_pythoneda(self, pkg) -> bool:
        """
        Checks if given package is from PythonEDA.
        :param pkg: The package.
        :type pkg: module
        :return: True in such case.
        :rtype: bool
        """
        if pkg.__name__ == "pythoneda":
            result = True
        elif pkg.__name__ == "" or pkg.__name__ == pkg.__package__:
            result = False
        else:
            result = False
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                try:
                    result = self.from_pythoneda(
                        importlib.import_module(pkg.__package__)
                    )
                except ModuleNotFoundError as err:
                    PythonEDA.log_error(f"Cannot import {pkg.__package__}: {err}")
        return result

    def load_all_packages(self):
        """
        Loads all packages.
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            for importer, pkg, ispkg in pkgutil.iter_modules():
                if (
                    pkg != "pythoneda"
                    and pkg != "tkinter"
                    and pkg != "matplotlib_inline"
                ):
                    if ispkg:
                        loader = importer.find_module(pkg)
                        try:
                            loader.load_module(pkg)
                        except Exception as err:
                            PythonEDA.log_error(f"Cannot import {pkg}: {err}")

        self.load_module_recursive("pythoneda")

    def load_module_recursive(self, name):
        """
        Loads given module, recursively.
        """
        try:
            # Try to load the module/package
            module = __import__(name, fromlist=[""])

            # If it's a package, discover its submodules and load them
            if pkgutil.get_loader(name).is_package(name):
                pkg_path = module.__path__
                for _, mod_name, ispkg in pkgutil.iter_modules(pkg_path):
                    self.load_module_recursive(f"{name}.{mod_name}")

        except ImportError as err:
            PythonEDA.log_error(f"Cannot import {name}: {err}")

    @staticmethod
    def custom_sort(item):
        split_item = item.split(".")
        return len(split_item), split_item

    def is_empty_namespace_folder(self, directory: str) -> bool:
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
            if os.path.isfile(path) and name == "__init__.py":
                has_init = True

            # Check if the file is not __init__.py
            if os.path.isfile(path) and name != "__init__.py" and name.endswith(".py"):
                has_other_py_files = True

            # Check if there are subdirectories
            if os.path.isdir(path):
                has_subfolders = True

        # Condition to make sure __init__.py is the only py file and there are subdirectories
        return has_init and has_subfolders and not has_other_py_files

    @staticmethod
    def find_actual_root_pythoneda_package_path() -> str:
        """
        Retrieves the path of the actual root Pythoneda package.
        :return: Such package.
        :rtype: str
        """
        result = None
        for path in sys.path:
            init_file = Path(path) / "pythoneda" / "shared" / Path("__init__.py")
            event_file = Path(path) / "pythoneda" / "shared" / Path("event.py")
            port_file = Path(path) / "pythoneda" / "shared" / Path("port.py")
            if (
                os.path.exists(init_file)
                and os.path.exists(event_file)
                and os.path.exists(port_file)
            ):
                result = str(Path(path) / "pythoneda")
                break
        return result

    def find_root_of(self, path: str) -> str:
        """
        Traverses the parents of given path until it reaches the "site-packages".
        :param path: The path.
        :type path: str
        :return: The root path.
        :rtype: str
        """
        working_path = path
        while True:
            if os.path.basename(working_path) == "site-packages":
                return os.path.abspath(working_path)

            parent = os.path.dirname(working_path)

            if parent == working_path:
                return path

            working_path = parent

    def get_path_of_packages_under_namespace(self, namespace: str) -> Dict:
        """
        Retrieves the paths of packages under given namespace.
        :param namespace: The namespace.
        :type namespace: str
        :return: A dictionary of package names and paths.
        :rtype: Dict[str, str]
        """
        result = {}

        for path in sys.path:
            init_file = Path(path) / namespace / Path("__init__.py")
            if os.path.exists(init_file):
                # walk through all files and directories in site-packages
                for root, dirs, _ in os.walk(path):
                    # only consider directories
                    for dir in dirs:
                        # construct the full path
                        full_path = os.path.join(root, dir)

                        # if this directory is a package
                        if os.path.isfile(os.path.join(full_path, "__init__.py")):
                            # get the package name
                            package_name = full_path[len(path) + 1 :].replace(
                                os.sep, "."
                            )

                            # if the package is a sub-package of the namespace
                            if package_name.startswith(namespace) and not result.get(
                                package_name, False
                            ):
                                result[package_name] = full_path

        result["pythoneda"] = self.find_actual_root_pythoneda_package_path()

        return result

    def load_pythoneda_packages(self) -> tuple:
        """
        Loads the PythonEDA-related packages.
        :return: A tuple consisting of (domain packages, domain modules, infrastructure packages, infrastructure modules).
        :rtype: tuple
        """
        (
            domain_packages,
            domain_modules,
            infrastructure_packages,
        ) = self.load_packages_under("pythoneda")

        extra_namespaces = os.environ.get("PYTHONEDA_EXTRA_NAMESPACES")
        if extra_namespaces is not None:
            for namespace in extra_namespaces.split(":"):
                (
                    extra_domain_packages,
                    extra_domain_modules,
                    extra_infrastructure_packages,
                ) = self.load_packages_under(namespace)
                self.__class__.extend_missing_items(
                    domain_packages, extra_domain_packages
                )
                self.__class__.extend_missing_items(
                    domain_modules, extra_domain_modules
                )
                self.__class__.extend_missing_items(
                    infrastructure_packages, extra_infrastructure_packages
                )
        return domain_packages, domain_modules, infrastructure_packages

    def load_packages_under(self, namespace: str) -> tuple:
        """
        Loads packages under given namespace.
        :param namespace: The namespace.
        :type namespace: str
        :return: A tuple consisting of (domain packages, domain modules, infrastructure packages, infrastructure modules).
        :rtype: tuple
        """

        domain_packages = []
        domain_modules = []
        infrastructure_packages = []
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            packages = self.get_path_of_packages_under_namespace(namespace)
            for package_name in packages:
                try:
                    package = __import__(package_name, fromlist=[""])
                    package = importlib.reload(package)
                    package_path = packages[package_name]
                    domain_package = Bootstrap.instance().is_domain_package(
                        package_path
                    )
                    infrastructure_package = (
                        Bootstrap.instance().is_infrastructure_package(package_path)
                    )
                    if domain_package:
                        if package_path not in domain_packages:
                            domain_packages.append(package_path)
                        submodules = Bootstrap.instance().import_submodules(
                            package, True, HexagonalLayer.DOMAIN
                        )
                        self.__class__.extend_missing_items(
                            domain_modules, submodules.values()
                        )
                    if infrastructure_package:
                        if package_path not in infrastructure_packages:
                            infrastructure_packages.append(package_path)
                except Exception as err:
                    PythonEDA.log_error(f"Cannot import {package_name}: {err}")

        return domain_packages, domain_modules, infrastructure_packages

    def find_domain_ports(self, modules: List) -> List:
        """
        Retrieves the port interfaces.
        :param modules: The modules to process.
        :type modules: List
        :return: Such interfaces.
        :rtype: List
        """
        result = []
        from pythoneda.shared.port import Port
        from pythoneda.shared.primary_port import PrimaryPort

        for module in modules:
            if Bootstrap.instance().is_domain_module(module):
                # PrimaryPorts get resolved independently
                interfaces = Bootstrap.instance().get_interfaces_of_module(
                    Port, module, PrimaryPort
                )
                self.__class__.extend_missing_items(result, interfaces)
        return result

    @classmethod
    def config_default_logging(cls):
        if not PythonEDA._default_logging_configured:
            initial_level = logging.DEBUG
            default_logger = logging.getLogger()
            handlers_to_remove = []
            for handler in default_logger.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handlers_to_remove.append(handler)
            for handler in handlers_to_remove:
                default_logger.removeHandler(handler)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(initial_level)
            formatter = logging.Formatter(
                "%(asctime)s [%(name)s] - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_handler.setFormatter(formatter)
            default_logger.setLevel(initial_level)
            default_logger.addHandler(console_handler)
            for name in ["asyncio", "git"]:
                specific_logger = logging.getLogger(name)
                specific_logger.setLevel(logging.WARNING)
            PythonEDA._default_logging_configured = True

    @classmethod
    def log_debug(cls, message: str):
        """
        Prints a debug message.
        :param message: The message to log.
        :type message: str
        """
        if PythonEDA._default_logging_configured:
            logging.getLogger("pythoneda.shared.application.PythonEDA").debug(message)

    @classmethod
    def log_info(cls, message: str):
        """
        Prints an info message.
        :param message: The message to log.
        :type message: str
        """
        if PythonEDA._default_logging_configured:
            logging.getLogger("pythoneda.shared.application.PythonEDA").info(message)
        else:
            sys.stdout.write(f"{message}\n")

    @classmethod
    def log_error(cls, message: str):
        """
        Prints an info message.
        :param message: The message to log.
        :type message: str
        """
        if PythonEDA._default_logging_configured:
            logging.getLogger("pythoneda.shared.application.PythonEDA").error(message)
        else:
            sys.stderr.write(f"{message}\n")

    @classmethod
    async def main(cls, name: str):
        """
        Runs the application from the command line.
        :param name: The application name.
        :type name: str
        """
        instance = cls.instance()
        await instance.after_bootstrap()

        await instance.accept_input()

    @classmethod
    def instance(cls):
        """
        Retrieves the singleton instance.
        :return: Such instance.
        :rtype: pythoneda.shared.application.PythonEDA
        """
        if cls._singleton is None:
            cls._singleton = cls()
        return cls._singleton

    def initialize(self):
        """
        Initializes this instance.
        """
        mappings = {}
        if len(PythonEDA.enabled_infrastructure_modules) == 0:
            PythonEDA.log_error("No infrastructure modules enabled!\n")
        else:
            PythonEDA.enabled_infrastructure_modules.append(
                importlib.import_module(LoggingConfigCli.__module__)
            )
            PythonEDA.enabled_infrastructure_modules.append(
                importlib.import_module(LoggingAdapter.__module__)
            )
            PythonEDA.enabled_infrastructure_modules.append(
                importlib.import_module(
                    "pythoneda.shared.infrastructure.logging.logging_config"
                )
            )
            LoggingConfigCli().entrypoint(self)
            from pythoneda.shared.primary_port import PrimaryPort

            self._primary_ports = Bootstrap.instance().get_adapters(
                PrimaryPort, PythonEDA.enabled_infrastructure_modules
            )
            mappings[PrimaryPort] = self._primary_ports
            for port in self.domain_ports:
                implementations = Bootstrap.instance().get_adapters(
                    port, PythonEDA.enabled_infrastructure_modules
                )
                if len(implementations) == 0:
                    if str(port.__module__) not in [
                        "pythoneda.shared.repo",
                        "pythoneda.shared.event_emitter",
                    ]:
                        PythonEDA.log_error(
                            f"[Warning] No implementations found for {port} in {PythonEDA.enabled_infrastructure_modules}\n"
                        )
                else:
                    mappings[port] = implementations

            from pythoneda.shared.ports import Ports

            Ports.initialize(mappings)

            from pythoneda.shared.event_listener import EventListener
            from pythoneda.shared.event_emitter import EventEmitter

            EventEmitter.register_receiver(self)

    def get_primary_port_instance(self, primaryPort):
        """
        Retrieves the primary port instance, if possible.
        :param primaryPort: The primary port.
        :type primaryPort: type[pythoneda.shared.PrimaryPort]
        :return: Such instance.
        :rtype: pythoneda.shared.PrimaryPort
        """
        from pythoneda.shared import Ports

        result = None
        if self.__class__.has_default_constructor(primaryPort):
            result = primaryPort()
        if result is None and self.__class__.has_instance_method(primaryPort):
            result = primaryPort.instance()
        if result is None and self.__class__.has_constructor_with_app_argument(
            primaryPort
        ):
            result = primaryPort(self)

        return result

    def delegate_priority(self, primaryPort) -> int:
        """
        Delegates the priority information to given primary port.
        :param primaryPort: The primary port.
        :type primaryPort: type[pythoneda.shared.PrimaryPort]
        :return: Such priority.
        :rtype: int
        """
        result = -1
        if self.__class__.has_default_priority_class_method(primaryPort):
            result = primaryPort.default_priority()

        if self.__class__.has_priority_class_method(primaryPort):
            result = primaryPort.priority()

        return result

    @classmethod
    def has_default_constructor(cls, targetClass) -> bool:
        """
        Checks if given class defines the default constructor or not.
        :param targetClass: The class to analyze.
        :type targetClass: type
        """
        init_signature = inspect.signature(targetClass.__init__)

        # Check if all parameters except 'self' have defaults
        parameters = init_signature.parameters.values()
        result = all(
            p.default is not inspect.Parameter.empty or p.name == "self"
            for p in parameters
        )

        return result

    @classmethod
    def has_instance_method(cls, targetClass) -> bool:
        """
        Checks if given class defines an instance() method or not.
        :param targetClass: The class to analyze.
        :type targetClass: type
        :return: True if the class defines that method.
        :rtype: bool
        """
        return cls.has_class_method(targetClass, "instance")

    @classmethod
    def has_constructor_with_app_argument(cls, targetClass) -> bool:
        """
        Checks if the constructor of given class defines an "app" as argument or not.
        :param targetClass: The class to analyze.
        :type targetClass: type
        """
        init_signature = inspect.signature(targetClass.__init__)

        # Check if all parameters except 'self' or 'app' have defaults.
        parameters = init_signature.parameters.values()
        result = all(
            p.default is not inspect.Parameter.empty
            or p.name == "self"
            or p.name == "app"
            for p in parameters
        )

        return result

    @classmethod
    def has_priority_class_method(cls, targetClass) -> bool:
        """
        Checks if given class defines a priority() method or not.
        :param targetClass: The class to analyze.
        :type targetClass: type
        :return: True if the class defines that method.
        :rtype: bool
        """
        return cls.has_class_method(targetClass, "priority")

    @classmethod
    def has_default_priority_class_method(cls, targetClass) -> bool:
        """
        Checks if given class defines a default_priority() method or not.
        :param targetClass: The class to analyze.
        :type targetClass: type
        :return: True if the class defines that method.
        :rtype: bool
        """
        return cls.has_class_method(targetClass, "default_priority")

    @classmethod
    def has_class_method(cls, targetClass, methodName: str) -> bool:
        """
        Checks if given class defines a given method or not.
        :param targetClass: The class to analyze.
        :type targetClass: type
        :param methodName: The method name.
        :type methodName: str
        :return: True if the class defines that method.
        :rtype: bool
        """
        return hasattr(targetClass, methodName) and callable(
            getattr(targetClass, methodName)
        )

    async def accept_input(self):
        """
        Notification the application has been launched from the CLI.
        """
        for primary_port in sorted(self.primary_ports, key=self.delegate_priority):
            if primary_port != LoggingConfigCli and (
                not self.one_shot or primary_port.is_one_shot_compatible
            ):
                previous_one_shot = self.one_shot
                port = self.get_primary_port_instance(primary_port)
                if port is not None:
                    await port.entrypoint(self)
                    one_shot_changed = previous_one_shot != self.one_shot

    async def after_bootstrap(self):
        """
        Hook to run code after the bootstrap process.
        """
        pass

    async def accept(self, event):  # : Event) -> Event:
        """
        Accepts and processes an event, potentially generating others in response.
        :param event: The event to process.
        :type event: pythoneda.shared.Event
        :return: The generated events in response.
        :rtype: List
        """
        result = []
        if event:
            first_events = []
            from pythoneda.shared import EventListener, PrimaryPort

            for listener_class in EventListener.listeners_for(event.__class__):
                if not self.one_shot or (
                    not issubclass(listener_class, PrimaryPort)
                    or listener_class.is_one_shot_compatible
                ):
                    PythonEDA.log_debug(
                        f"Delegating {event.__class__.full_class_name()} to {listener_class.full_class_name()}"
                    )
                    resulting_events = await listener_class.accept(event)
                    for new_event in resulting_events:
                        asyncio.create_task(self.emit(new_event))
                    if resulting_events and len(resulting_events) > 0:
                        self.__class__.extend_missing_items(
                            first_events, resulting_events
                        )
            if len(first_events) > 0:
                self.__class__.extend_missing_items(result, first_events)

        await asyncio.gather()

        aux = []
        for evt in result:
            self.__class__.extend_missing_items(aux, await self.accept(evt))

        self.__class__.extend_missing_items(result, aux)

        return result

    @staticmethod
    async def emit(event):
        """
        Emits given event.
        :param event: The event to emit.
        :type event: pythoneda.shared.Event
        """
        if event:
            from pythoneda.shared import EventEmitter, Ports

            event_emitter = Ports.instance().resolve(EventEmitter)
            if event_emitter is not None:
                PythonEDA.log_debug(f"Emitting {event.__class__}")
                await event_emitter.emit(event)

    def accept_configure_logging(self, logConfig: Dict[str, bool]):
        """
        Receives information about the logging settings.
        :param logConfig: The logging config.
        :type logConfig: Dict[str, bool]
        """
        module_function = self.__class__.get_log_config()
        if module_function:
            module_function(logConfig["info"], logConfig["debug"], logConfig["quiet"])

        quiet = logConfig["quiet"]
        if not quiet and self.banner is not None:
            self.banner.print()

    def accept_one_shot(self, flag: bool):
        """
        Marks one-shot behavior as active or inactive.
        :param flag: Such behavior.
        :type flag: bool
        """
        self.one_shot = flag

    def accept_configure_eventsourcing(self, config: Dict[str, str]):
        """
        Receives information about the eventsourcing settings.
        :param config: The config.
        :type config: Dict[str, str]
        """
        module = config.get("PERSISTENCE_MODULE", None)
        if module:
            os.environ["PERSISTENCE_MODULE"] = module
            self.apply_eventsourcing()
        esdb_uri = config.get("EVENTSTOREDB_URI", None)
        if esdb_uri:
            os.environ["EVENTSTOREDB_URI"] = esdb_uri
        esdb_root_certificates = config.get("EVENTSTOREDB_ROOT_CERTIFICATES", None)
        if esdb_root_certificates:
            os.environ["EVENTSTOREDB_ROOT_CERTIFICATES"] = esdb_root_certificates
        sqlite_db_name = config.get("SQLITE_DBNAME", None)
        if sqlite_db_name:
            os.environ["SQLITE_DBNAME"] = sqlite_db_name

    def apply_eventsourcing(self):
        """
        Performs changes in PythonEDA classes to support event sourcing.
        """
        from pythoneda.shared import Entity, Event, ValueObject
        from eventsourcing.domain import Aggregate

        Entity.__bases__ = (ValueObject, Aggregate)
        Event.__bases__ = (ValueObject, Aggregate.Event)

    @classmethod
    def get_log_config(cls) -> Callable:
        """
        Retrieves the function to configure the logging system.
        :return: Such function.
        :rtype: Callable
        """
        result = None

        for module in PythonEDA.enabled_infrastructure_modules:
            if (
                module.__name__
                == "pythoneda.shared.infrastructure.logging.logging_config"
            ):
                entry = {}
                configure_logging_function = getattr(module, "configure_logging", None)
                if callable(configure_logging_function):
                    result = configure_logging_function
                else:
                    sys.stderr.write(f"Error in {module.__file__}: configure_logging\n")
        return result

    @classmethod
    def extend_missing_items(cls, first: List, second: List):
        """
        Adds the items of the second list into the first list, excluding those already included.
        :param first: The first list.
        :type first: List
        :param second: The second list.
        :type second: List
        """
        [first.append(item) for item in second if item not in first]

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """
        Initializes this class.
        :param kwargs: Any additional keyword arguments.
        :type kwargs: Dict
        """
        super().__init_subclass__(**kwargs)
        PythonEDA.config_default_logging()


import asyncio
import importlib
import importlib.util
import os
import sys

if __name__ == "__main__":
    asyncio.run(PythonEDA.main("pythoneda.shared.application.PythonEDA"))
# vim: syntax=python ts=4 sw=4 sts=4 tw=79 sr et
# Local Variables:
# mode: python
# python-indent-offset: 4
# tab-width: 4
# indent-tabs-mode: nil
# fill-column: 79
# End:
