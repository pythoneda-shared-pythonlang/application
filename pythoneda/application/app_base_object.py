"""
pythoneda/app_base_object.py

This script defines the AppBaseObject class.

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
import logging

class AppBaseObject():
    """
    Ancestor of all pythoneda.application classes.

    Class name: AppBaseObject

    Responsibilities:
        - Define common behavior for all pythoneda.application classes.

    Collaborators:
        - None
    """
    @classmethod
    def logger(cls):
        """
        Retrieves the logger instance.
        :return: Such instance.
        :rtype: logging.Logger
        """
        return logging.getLogger(cls.__name__)
