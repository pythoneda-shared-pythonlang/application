"""
pythoneda/application/hexagonal_layer.py

This file declares HexagonalLayer class.

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
from enum import Enum, auto

class HexagonalLayer(Enum):
    """
    An enumerated type to identify layers in hexagonal architectures.

    Class name: HexagonalLayer

    Responsibilities:
        - Define the different types of layers.

    Collaborators:
        - None. But this class is used both by pythoneda.application.bootstrap and pythoneda.application.pythoneda.PythonEDA
    """
    DOMAIN = auto()
    INFRASTRUCTURE = auto()
    APPLICATION = auto()
