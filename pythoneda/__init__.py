"""
pythoneda/__init__.py

This file ensures pythoneda is a namespace.

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
__path__ = __import__('pkgutil').extend_path(__path__, __name__)

# default log level to be overridden by cli flags
import logging
if not logging.getLogger().hasHandlers():
    import sys
    initial_level = logging.DEBUG
    default_logger = logging.getLogger()
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(initial_level)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    default_logger.setLevel(initial_level)
    default_logger.addHandler(console_handler)
    for name in [ "asyncio" "git.cmd" ]:
        specific_logger = logging.getLogger(name)
        specific_logger.setLevel(logging.WARNING)

# Ugly hack to avoid sorting the PYTHONPATH
try:
    from pythoneda.port import Port
    from pythoneda.formatting import Formatting
    from pythoneda.sensitive_value import SensitiveValue
    from pythoneda.value_object import attribute, filter_attribute, internal_attribute, primary_key_attribute, sensitive, ValueObject
    from pythoneda.domain_exception import DomainException
    from pythoneda.unsupported_event import UnsupportedEvent
    from pythoneda.entity import Entity
    from pythoneda.entity_in_progress import EntityInProgress
    from pythoneda.event import Event
    from pythoneda.event_emitter import EventEmitter
    from pythoneda.event_listener import listen, EventListener
    from pythoneda.primary_port import PrimaryPort
    from pythoneda.ports import Ports
    from pythoneda.repo import Repo
except ImportError:
    pass
