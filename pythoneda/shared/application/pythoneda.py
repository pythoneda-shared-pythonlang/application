# vim: set fileencoding=utf-8
"""
pythoneda/shared/application/pythoneda.py

This file defines PythonEDA.

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
from .bootstrap import Bootstrap
from collections.abc import Iterable

# from eventsourcing.application import Application
import importlib
import inspect
import logging
import os
from pathlib import Path
import pkgutil
from pythoneda.shared import Invariant, Invariants, PythonedaApplication
from pythoneda.shared.banner import Banner
from pythoneda.shared.infrastructure.cli import LoggingConfigCli
from pythoneda.shared.infrastructure.logging import LoggingAdapter
import sys
from typing import Callable, Dict, List, Tuple, Type
import warnings


class PythonEDA(PythonedaApplication):
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
    _enabled_infrastructure_modules = []
    _enabled_infrastructure_adapters = []
    _logging_configured = False
    _pending_logging = []

    def __init__(self, name: str, banner=None, file=__file__):
        """
        Initializes the instance.
        :param name: The application name.
        :type name: str
        :param banner: The project's banner.
        :type banner: pythoneda.shared.banner.Banner
        :param file: The file where this specific instance is defined.
        :type file: str
        """
        super().__init__(name)
        self._primary_ports = []
        self._banner = banner
        self.fix_syspath(file)
        self.sort_pythoneda_package_in_sys_path()
        self.load_all_packages()
        (
            self._domain_packages,
            self._domain_modules,
            self._infrastructure_packages,
        ) = self.load_bounded_context()
        self._domain_ports = self.find_domain_ports(self._domain_modules)
        self._one_shot = False
        self.initialize()

    @classmethod
    def default_name(cls) -> str:
        """
        Retrieves the default name.
        :return: Such name.
        :rtype: str
        """
        module = cls.__module__
        if module == "__main__":
            module = ""
        else:
            module = f"{module}."
        return f"{module}{cls.__qualname__}"

    @classmethod
    @property
    def enabled_infrastructure_modules(cls) -> List:
        """
        Retrieves the enabled infrastructure modules.
        :return: Such list.
        :rtype: List
        """
        return cls._enabled_infrastructure_modules

    @classmethod
    @property
    def enabled_infrastructure_adapters(cls) -> List:
        """
        Retrieves the enabled infrastructure adapters.
        :return: Such list.
        :rtype: List
        """
        return cls._enabled_infrastructure_adapters

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
                        # Bootstrap.instance().import_package(pkg.__package__)
                        importlib.import_module(pkg.__package__)
                    )
                except ModuleNotFoundError as err:
                    PythonEDA.log_error(
                        f"Cannot import pythoneda package {pkg.__package__}: {err}"
                    )
        return result

    def load_all_packages(self):
        """
        Loads all packages.
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            for importer, pkg, ispkg in pkgutil.iter_modules():
                if (
                    ispkg
                    and pkg
                    not in {"pythoneda", "asyncio", "tkinter", "matplotlib_inline"}
                    and pkg not in sys.modules
                ):
                    # Use find_spec instead of find_module
                    spec = importer.find_spec(pkg)
                    if spec is None:
                        PythonEDA.log_error(f"Spec is none for {pkg}")
                    else:
                        try:
                            # Load the module using the spec
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                        except Exception as err:
                            PythonEDA.log_error(
                                f"Cannot import package {pkg}/{type(pkg)}: {err}"
                            )

        self.load_module_recursive("pythoneda")

    def load_module_recursive(self, name):
        """
        Loads given module, recursively.
        """
        try:
            # Try to load the module/package
            #            module = Bootstrap.instance().import_package(name)
            module = __import__(name, fromlist=[""])

            # If it's a package, discover its submodules and load them
            if pkgutil.get_loader(name).is_package(name):
                pkg_path = module.__path__
                for _, mod_name, ispkg in pkgutil.iter_modules(pkg_path):
                    self.load_module_recursive(f"{name}.{mod_name}")

        except ImportError as err:
            PythonEDA.log_error(f"Cannot import module {name}: {err}")
        except Exception as err:
            PythonEDA.log_error(f"Cannot import module {name}: {err}")

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
                    if ".dist-info" in root:
                        continue
                    # only consider directories
                    for dir in dirs:
                        if dir == "__pycache__" or ".dist-info" in dir:
                            continue
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

    def load_bounded_context(self) -> Tuple[List, List, List]:
        """
        Loads the bounded context packages.
        :return: A tuple consisting of (domain packages, domain modules, infrastructure packages).
        :rtype: Tuple[List, List, List]
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
        self.log_debug_packages("Infrastructure packages:", infrastructure_packages)
        return domain_packages, domain_modules, infrastructure_packages

    def log_debug_packages(self, prefix: str, pkgs: List):
        """
        Logs the packages found.
        :param prefix: The message prefix,
        :type prefix: str
        :param pkgs: The packages.
        :type pkgs: List
        """
        bottom_subfolders = [
            os.path.basename(pkg.rstrip(os.sep))  # rstrip to handle trailing '/' or '\'
            for pkg in pkgs
        ]

        # Remove duplicates by converting to a set, then convert back to a list and sort
        PythonEDA.log_debug(f'{prefix} {", ".join(sorted(set(bottom_subfolders)))}')

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
            from pythoneda.shared.artifact import HexagonalLayer

            for package_name in packages:
                try:
                    # package = Bootstrap.instance().import_package(package_name)
                    package = __import__(package_name, fromlist=[""])
                    package = importlib.reload(package)
                    package_path = packages[package_name]
                    domain_package = Bootstrap.instance().is_domain_package(
                        package_path
                    )
                    infrastructure_package = (
                        Bootstrap.instance().is_infrastructure_package(package_path)
                    )
                    if domain_package and package_path not in domain_packages:
                        domain_packages.append(package_path)
                        PythonEDA.log_debug(f"Found domain package {package_path}")
                        submodules = Bootstrap.instance().import_submodules(
                            package, HexagonalLayer.DOMAIN, True
                        )
                        self.__class__.extend_missing_items(
                            domain_modules, submodules.values()
                        )
                    if (
                        infrastructure_package
                        and package_path not in infrastructure_packages
                    ):
                        infrastructure_packages.append(package_path)
                except Exception as err:
                    PythonEDA.log_error(f"Cannot import package {package_name}: {err}")
                    import traceback

                    traceback.print_exc()

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
            if module is not None:
                if Bootstrap.instance().is_domain_module(module):
                    # PrimaryPorts get resolved independently
                    interfaces = Bootstrap.instance().get_interfaces_of_module(
                        Port, module, PrimaryPort
                    )
                    # print(f"Interfaces of {module}: {interfaces}")
                    self.__class__.extend_missing_items(result, interfaces)

        return result

    @classmethod
    def log_debug(cls, message: str):
        """
        Prints a debug message.
        :param message: The message to log.
        :type message: str
        """
        if cls._logging_configured:
            cls.logger().debug(message)
        else:
            cls._pending_logging.append(("debug", message))

    @classmethod
    def log_info(cls, message: str):
        """
        Prints an info message.
        :param message: The message to log.
        :type message: str
        """
        if cls._logging_configured:
            cls.logger().info(message)
        else:
            cls._pending_logging.append(("info", message))

    @classmethod
    def log_error(cls, message: str):
        """
        Prints an info message.
        :param message: The message to log.
        :type message: str
        """
        if cls._logging_configured:
            cls.logger().error(message)
        else:
            cls._pending_logging.append(("error", message))

    @classmethod
    async def main(cls, name: str = None) -> PythonedaApplication:
        """
        Runs the application from the command line.
        :param name: The application name.
        :type name: str
        """
        result = await cls.instance(name)
        await result.accept_input()

        return result

    def bind_invariants(self):
        """
        Binds any invariants.
        """
        Invariants.instance().bind(
            Invariant[PythonedaApplication](
                self, "pythoneda.shared.PythonedaApplication"
            )
        )

    @classmethod
    async def instance(cls, name: str = None) -> PythonedaApplication:
        """
        Retrieves the singleton instance.
        :param name: The name.
        :type name: str
        :return: Such instance.
        :rtype: pythoneda.shared.PythonedaApplication
        """
        if cls._singleton is None:
            if name is None:
                name = cls.default_name()
            cls._singleton = cls(name)
            cls._singleton.bind_invariants()
            await cls._singleton.after_bootstrap()

        return cls._singleton

    def initialize(self):
        """
        Initializes this instance.
        """
        from pythoneda.shared.primary_port import PrimaryPort

        mappings = {}
        if len(PythonEDA.enabled_infrastructure_modules) == 0:
            PythonEDA.log_error("No infrastructure modules enabled!\n")
        else:
            PythonEDA.enabled_infrastructure_modules.append(
                Bootstrap.instance().import_package(LoggingConfigCli.__module__)
            )
            PythonEDA.enabled_infrastructure_modules.append(
                Bootstrap.instance().import_package(LoggingAdapter.__module__)
            )
            PythonEDA.enabled_infrastructure_modules.append(
                Bootstrap.instance().import_package(
                    "pythoneda.shared.infrastructure.logging.logging_config"
                )
            )

            aux = "\n".join([str(m) for m in PythonEDA.enabled_infrastructure_modules])
            PythonEDA.log_debug(f"Enabled infrastructure modules:\n{aux}")

            self._primary_ports = Bootstrap.instance().get_adapters(
                PrimaryPort, PythonEDA.enabled_infrastructure_modules
            )
            mappings[PrimaryPort] = self._primary_ports
            PythonEDA.log_debug(f"Domain ports: {self.domain_ports}")
            for port in self.domain_ports:
                implementations = Bootstrap.instance().get_adapters(
                    port, PythonEDA.enabled_infrastructure_modules
                )
                for adapter in PythonEDA.enabled_infrastructure_adapters:
                    if isinstance(adapter, port):
                        implementations.append(adapter)

                if len(implementations) == 0:
                    if str(port.__module__) not in [
                        "pythoneda.shared.repo",
                        "pythoneda.shared.event_emitter",
                        "pythoneda.shared.artifact.artifact_repository",
                    ]:
                        items = [
                            module.__name__
                            for module in PythonEDA.enabled_infrastructure_modules
                        ]
                        PythonEDA.log_info(
                            f"[Warning] No implementations found for {port} in {items}"
                        )
                else:
                    mappings[port] = implementations

            from pythoneda.shared.ports import Ports

            PythonEDA.log_debug(f"Initializing ports with mappings: {mappings}")
            Ports.initialize(mappings)

            self.__class__._logging_configured = True
            for level, message in self.__class__._pending_logging:
                if level == "debug":
                    PythonEDA.logger().debug(message)
                elif level == "info":
                    PythonEDA.logger().info(message)
                elif level == "error":
                    PythonEDA.logger().error(message)

            from pythoneda.shared.event_emitter import EventEmitter

            EventEmitter.register_receiver(self)

    def get_primary_port_instance(self, primaryPort: Type):
        """
        Retrieves the primary port instance, if possible.
        :param primaryPort: The primary port.
        :type primaryPort: Type[pythoneda.shared.PrimaryPort]
        :return: Such instance.
        :rtype: pythoneda.shared.PrimaryPort
        """
        return primaryPort()

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
        primary_ports = sorted(self.primary_ports, key=self.delegate_priority)
        primary_port_instances = []
        for primary_port in primary_ports:
            port = self.get_primary_port_instance(primary_port)
            primary_port_instances.append(port)
            await port.configure()

        for primary_port_instance in primary_port_instances:
            if primary_port_instance is not None:
                await primary_port_instance.entrypoint(self)

    async def after_bootstrap(self):
        """
        Hook to run code after the bootstrap process.
        """
        pass

    async def accept(self, eventOrEvents) -> List:
        """
        Accepts and processes an event, potentially generating others in response.
        :param eventOrEvents: The event(s) to process.
        :type eventOrEvents: Union[pythoneda.shared.Event, collections.abc.Iterable]
        :return: The generated events in response.
        :rtype: List[pythoneda.shared.Event]
        """
        result = []
        if eventOrEvents:
            first_events = []
            from pythoneda.shared import EventListener, PrimaryPort

            if isinstance(eventOrEvents, Iterable):
                events = eventOrEvents
            else:
                events = [eventOrEvents]
            for event in events:
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
                triggered = await event.maybe_trigger()
                if len(triggered) > 0:
                    self.__class__.extend_missing_items(first_events, triggered)

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

            event_emitters = Ports.instance().resolve(EventEmitter)
            for event_emitter in event_emitters:
                if event_emitter is not None:
                    await event_emitter.emit(event)

    def accept_configure_logging(self, logConfig: Dict[str, bool]):
        """
        Receives information about the logging settings.
        :param logConfig: The logging config.
        :type logConfig: Dict[str, bool]
        """
        module_function = self.__class__.get_log_config()
        if module_function:
            module_function(
                logConfig["info"],
                logConfig["debug"],
                logConfig["trace"],
                logConfig["quiet"],
            )

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
                    PythonEDA.log_error(
                        f"Error in {module.__file__}: configure_logging"
                    )
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

    def application_packages(self):
        """
        Retrieves the application packages.
        :return: Such packages.
        :rtype: List
        """
        # Get the module's fully qualified name
        module_name = self.__class__.__module__

        # Split the module name and build the list of progressively longer package paths
        parts = module_name.split(".")
        return [".".join(parts[: i + 1]) for i in range(len(parts))]


import asyncio
import importlib
import importlib.util
import os
import sys

if __name__ == "__main__":
    asyncio.run(PythonEDA.main())
# vim: syntax=python ts=4 sw=4 sts=4 tw=79 sr et
# Local Variables:
# mode: python
# python-indent-offset: 4
# tab-width: 4
# indent-tabs-mode: nil
# fill-column: 79
# End:
