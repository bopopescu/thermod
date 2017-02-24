# -*- coding: utf-8 -*-
"""Init of `thermod` package.

Copyright (C) 2017 Simone Rossetto <simros85@gmail.com>

This file is part of Thermod.

Thermod is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Thermod is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Thermod.  If not, see <http://www.gnu.org/licenses/>.
"""

from thermod.config import JsonValueError, ScriptError, LogStyleAdapter
from thermod.heating import BaseHeating, ScriptHeating, PiPinsRelayHeating, \
    HeatingError, ScriptHeatingError
from thermod.socket import ControlThread, ControlServer, ControlRequestHandler
from thermod.timetable import TimeTable, ShouldBeOn
from thermod.thermometer import BaseThermometer, ScriptThermometer, \
    PiAnalogZeroThermometer, ThermometerError, ScriptThermometerError

# No import of memento module because it is not specific to Thermod daemon,
# it is here only for convenience. If someone wants to use its functionality
# he/she can manually import thermod.memento.

# vim: fileencoding=utf-8 tabstop=4 shiftwidth=4 expandtab