from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Literal

import numpy as np

from qcodes.instrument import VisaInstrument, VisaInstrumentKWArgs
from qcodes.instrument.parameter import Parameter, MultiParameter
from qcodes.math_utils import FieldVector
from qcodes.parameters import (
    Parameter,
    create_on_off_val_mapping,
)
from qcodes.utils.validators import (
    Enum,
    Ints,
    Lists,
    MultiType,
    Numbers,
    Strings,
)

if TYPE_CHECKING:
    from typing_extensions import Unpack

    from qcodes.parameters import Parameter


class Keithley2400(VisaInstrument):
    """
    Extended QCoDeS driver for the Keithley 2400 SourceMeter.

    This driver builds upon the basic driver and adds several functionalities based on the
    information from the manual, including:

        - Support for 2-wire and 4-wire sensing modes.
        - Implementation of guarding techniques (cable guard and ohms guard).
        - Integration of source delay for improved settling time.
        - Handling of different trigger modes and the Trigger Link interface.
        - Data buffering and storage using the internal buffer.
        - Support for basic sweep operations (linear staircase).

    """

    default_terminator = "\n"

    def __init__(
        self,
        name: str,
        address: str,
        **kwargs: "Unpack[VisaInstrumentKWArgs]",
    ):
        super().__init__(name, address, **kwargs)

        self._model: str = self.IDN()["model"]  # Store the model number

        # Sensing Mode
        self.add_parameter(
            "sense_mode",
            get_cmd=":SYSTem:RSENse?",
            set_cmd=":SYSTem:RSENse {}",
            vals=Enum("local", "remote"),
            docstring="Selects between 2-wire local sensing and 4-wire remote sensing.",
        )

        # Guarding
        self.add_parameter(
            "guard_mode",
            get_cmd=":SYSTem:GUARd?",
            set_cmd=":SYSTem:GUARd {}",
            vals=Enum("cable", "ohms"),
            docstring="Selects between cable guard and ohms guard.",
        )

        # Source Delay
        self.add_parameter(
            "source_delay",
            unit="s",
            get_cmd=":SOURce:DELay?",
            set_cmd=":SOURce:DELay {:.6f}",
            vals=Numbers(0, 9999.999),
            docstring="Sets the delay time between setting the source value and taking a measurement.",
        )

        self.add_parameter(
            "auto_source_delay_enabled",
            get_cmd=":SOURce:DELay:AUTO?",
            set_cmd=":SOURce:DELay:AUTO {}",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0"),
            docstring="Enables or disables the automatic source delay."
        )


        # Triggering
        self.add_parameter(
            "trigger_source",
            get_cmd=":TRIGger:SOURce?",
            set_cmd=":TRIGger:SOURce {}",
            vals=Enum("immediate", "timer", "bus", "external"),
            docstring="Selects the trigger source for measurements.",
        )

        self.add_parameter(
            "trigger_count",
            get_cmd=":TRIGger:COUNt?",
            set_cmd=":TRIGger:COUNt {}",
            vals=Ints(1, 2500),
            docstring="Sets the trigger count for measurements.",
        )

        self.add_parameter(
            "trigger_delay",
            unit="s",
            get_cmd=":TRIGger:DELay?",
            set_cmd=":TRIGger:DELay {:.6f}",
            vals=Numbers(0, 9999.999),
            docstring="Sets the delay time between the trigger event and the start of the measurement.",
        )

        # Trigger Link (Refer to Chapter 11 for details)
        # For now, let's just implement the output trigger settings (assuming line #2)
        self.add_parameter(
            "trigger_out_enabled",
            get_cmd=":TRIGger:OUTPut:STATe?",
            set_cmd=":TRIGger:OUTPut:STATe {}",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0"),
            docstring="Enables or disables the output trigger pulse."
        )

        self.add_parameter(
            "trigger_out_event",
            get_cmd=":TRIGger:OUTPut:EVENt?",
            set_cmd=":TRIGger:OUTPut:EVENt {}",
            vals=Enum("source", "delay", "measure"),
            docstring="Selects the trigger model event that generates the output trigger pulse.",
        )

        # Data Buffer
        self.add_parameter(
            "buffer_size",
            get_cmd=":TRACe:POINts?",
            set_cmd=":TRACe:POINts {}",
            vals=Ints(1, 2500),
            docstring="Sets the size of the internal data buffer."
        )

        self.add_parameter(
            "buffer_enabled",
            get_cmd=":TRACe:FEED:CONTrol?",
            set_cmd=":TRACe:FEED:CONTrol {}",
            vals=Enum("next", "never"),
            docstring="Controls whether data is stored in the buffer ('next') or not ('never')."
        )

        self.add_parameter(
            "buffer_read",
            get_cmd=":TRACe:DATA?",
            docstring="Reads the data stored in the buffer.",
        )

        self.add_parameter(
            'beeper_enabled',
            get_cmd=':SYSTem:BEEPer:STATe?',
            set_cmd=':SYSTem:BEEPer:STATe {}',
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0"),
        )

        # Sweep (Linear Staircase - See Chapter 10 for details)
        self.add_parameter(
            "sweep_start",
            unit="V",
            get_cmd=":SOURce:VOLTage:STARt?",
            set_cmd=":SOURce:VOLTage:STARt {}",
            vals=Numbers(),
            docstring="Sets the starting voltage for a linear staircase sweep.",
        )

        self.add_parameter(
            "sweep_stop",
            unit="V",
            get_cmd=":SOURce:VOLTage:STOP?",
            set_cmd=":SOURce:VOLTage:STOP {}",
            vals=Numbers(),
            docstring="Sets the stopping voltage for a linear staircase sweep.",
        )

        self.add_parameter(
            "sweep_step",
            unit="V",
            get_cmd=":SOURce:VOLTage:STEP?",
            set_cmd=":SOURce:VOLTage:STEP {}",
            vals=Numbers(),
            docstring="Sets the voltage step size for a linear staircase sweep.",
        )

        self.add_parameter(
            "sweep_points",
            get_cmd=":SOURce:SWEep:POINts?",
            set_cmd=":SOURce:SWEep:POINts {}",
            vals=Ints(2, 2500),
            docstring="Sets the number of points for a linear staircase sweep.",
        )

        self.add_parameter(
            "sweep_ranging",
            get_cmd=":SOURce:SWEep:RANGing?",
            set_cmd=":SOURce:SWEep:RANGing {}",
            vals=Enum("best", "auto", "fixed"),
            docstring="Selects the source ranging mode during a sweep."
        )

        self.add_parameter(
            "sweep_mode",
            get_cmd=":SOURce:VOLTage:MODE?",
            set_cmd=":SOURce:VOLTage:MODE {}",
            vals=Enum("fixed", "sweep"),
            docstring="Selects between fixed voltage output and sweep mode.",
        )

        self.add_function(
            "run_sweep",
            call_cmd=":INITiate",
            docstring="Initiates a sweep when in sweep mode.",
        )

        # Additional parameters from the basic driver

        self.rangev: Parameter = self.add_parameter(
            "rangev",
            get_cmd="SENS:VOLT:RANG?",
            get_parser=float,
            set_cmd="SOUR:VOLT:RANG {:f}",
            label="Voltage range",
        )
        """Parameter rangev"""

        self.rangei: Parameter = self.add_parameter(
            "rangei",
            get_cmd="SENS:CURR:RANG?",
            get_parser=float,
            set_cmd="SOUR:CURR:RANG {:f}",
            label="Current range",
        )
        """Parameter rangei"""

        self.compliancev: Parameter = self.add_parameter(
            "compliancev",
            get_cmd="SENS:VOLT:PROT?",
            get_parser=float,
            set_cmd="SENS:VOLT:PROT {:f}",
            label="Voltage Compliance",
        )
        """Parameter compliancev"""

        self.compliancei: Parameter = self.add_parameter(
            "compliancei",
            get_cmd="SENS:CURR:PROT?",
            get_parser=float,
            set_cmd="SENS:CURR:PROT {:f}",
            label="Current Compliance",
        )
        """Parameter compliancei"""

        self.volt: Parameter = self.add_parameter(
            "volt",
            get_cmd=self._get_read_output_protected,
            get_parser=self._volt_parser,
            set_cmd=":SOUR:VOLT:LEV {:.8f}",
            label="Voltage",
            unit="V",
            docstring="Sets voltage in 'VOLT' mode. "
            "Get returns measured voltage if "
            "sensing 'VOLT' otherwise it returns "
            "setpoint value. "
            "Note that it is an error to read voltage with "
            "output off",
        )
        """Sets voltage in 'VOLT' mode. Get returns measured voltage if sensing 'VOLT' otherwise it returns setpoint value. Note that it is an error to read voltage with output off"""

        self.curr: Parameter = self.add_parameter(
            "curr",
            get_cmd=self._get_read_output_protected,
            get_parser=self._curr_parser,
            set_cmd=":SOUR:CURR:LEV {:.8f}",
            label="Current",
            unit="A",
            docstring="Sets current in 'CURR' mode. "
            "Get returns measured current if "
            "sensing 'CURR' otherwise it returns "
            "setpoint value. "
            "Note that it is an error to read current with "
            "output off",
        )
        """Sets current in 'CURR' mode. Get returns measured current if sensing 'CURR' otherwise it returns setpoint value. Note that it is an error to read current with output off"""

        self.mode: Parameter = self.add_parameter(
            "mode",
            vals=Enum("VOLT", "CURR"),
            get_cmd=":SOUR:FUNC?",
            set_cmd=self._set_mode_and_sense,
            label="Mode",
        )
        """Parameter mode"""

        self.sense: Parameter = self.add_parameter(
            "sense",
            vals=Strings(),
            get_cmd=":SENS:FUNC?",
            set_cmd=':SENS:FUNC "{:s}"',
            label="Sense mode",
        )
        """Parameter sense"""

        self.output: Parameter = self.add_parameter(
            "output",
            set_cmd=":OUTP:STAT {}",
            get_cmd=":OUTP:STAT?",
            val_mapping=create_on_off_val_mapping(on_val="1", off_val="0"),
        )
        """Parameter output"""

        self.nplcv: Parameter = self.add_parameter(
            "nplcv",
            get_cmd="SENS:VOLT:NPLC?",
            get_parser=float,
            set_cmd="SENS:VOLT:NPLC {:f}",
            label="Voltage integration time",
        )
        """Parameter nplcv"""

        self.nplci: Parameter = self.add_parameter(
            "nplci",
            get_cmd="SENS:CURR:NPLC?",
            get_parser=float,
            set_cmd="SENS:CURR:NPLC {:f}",
            label="Current integration time",
        )
        """Parameter nplci"""

        self.resistance: Parameter = self.add_parameter(
            "resistance",
            get_cmd=self._get_read_output_protected,
            get_parser=self._resistance_parser,
            label="Resistance",
            unit="Ohm",
            docstring="Measure resistance from current and voltage. "
            "Note that it is an error to read current "
            "and voltage with output off",
        )
        """Measure resistance from current and voltage. Note that it is an error to read current and voltage with output off"""

        self.write(":TRIG:COUN 1;:FORM:ELEM VOLT,CURR")
        # This line sends 2 commands to the instrument:
        # ":TRIG:COUN 1" sets the trigger count to 1 so that each READ? returns
        # only 1 measurement result.
        # ":FORM:ELEM VOLT,CURR" sets the output string formatting of the the
        # Keithley 2400 to return "{voltage}, {current}".
        # Default value on instrument reset is "VOLT, CURR, RES, TIME, STATUS";
        # however, resistance, status, and time are unused in this driver and
        # so are omitted.
        # These commands do not reset the instrument but do the minimal amount
        # to ensure that voltage and current parameters can be read from the
        # instrument, in the event that output formatting of the instrument was
        # previously changed to some other unknown state.

        self.connect_message()

    def _get_read_output_protected(self) -> str:
        """
        This wrapper function around ":READ?" exists because calling
        ":READ?" on an instrument with output disabled is an error.
        So first we check that output is on and if not we return
        nan for volt, curr etc.
        """
        output = self.output.get_latest()
        if output is None:
            # if get_latest returns None we have
            # to ask the instrument for the status of output
            output = self.output.get()

        if output == 1:
            msg = self.ask(":READ?")
        else:
            raise RuntimeError("Cannot perform read with output off")
        return msg

    def _set_mode_and_sense(self, msg: str) -> None:
        # This helps set the correct read out curr/volt
        if msg == "VOLT":
            self.sense("CURR")
        elif msg == "CURR":
            self.sense("VOLT")
        else:
            raise AttributeError("Mode does not exist")
        self.write(f":SOUR:FUNC {msg:s}")

    def reset(self) -> None:
        """
        Reset the instrument. When the instrument is reset, it performs the
        following actions.

            Returns the SourceMeter to the GPIB default conditions.

            Cancels all pending commands.

            Cancels all previously send `*OPC` and `*OPC?`
        """
        self.write(":*RST")

    def _volt_parser(self, msg: str) -> float:
        fields = [float(x) for x in msg.split(",")]
        return fields[0]

    def _curr_parser(self, msg: str) -> float:
        fields = [float(x) for x in msg.split(",")]
        return fields[1]

    def _resistance_parser(self, msg: str) -> float:
        fields = [float(x) for x in msg.split(",")]
        res = fields[0] / fields[1]
        return res


    # Extended Functionality

    def get_compliance(self, mode: Literal['VOLT', 'CURR']) -> float:
        """
        Gets the compliance value for the specified mode.

        Args:
            mode: 'VOLT' or 'CURR'

        Returns:
            Compliance value (float)
        """
        if mode == 'VOLT':
            return self.compliancev()
        elif mode == 'CURR':
            return self.compliancei()
        else:
            raise ValueError("Invalid mode. Choose either 'VOLT' or 'CURR'.")

    def set_compliance(self, mode: Literal['VOLT', 'CURR'], value: float) -> None:
        """
        Sets the compliance value for the specified mode.

        Args:
            mode: 'VOLT' or 'CURR'
            value: Compliance value (float)
        """
        if mode == 'VOLT':
            self.compliancev(value)
        elif mode == 'CURR':
            self.compliancei(value)
        else:
            raise ValueError("Invalid mode. Choose either 'VOLT' or 'CURR'.")

    def set_output_range(self, mode: Literal['VOLT', 'CURR'], value: float) -> None:
        """
        Sets the output range for the specified mode.

        Args:
            mode: 'VOLT' or 'CURR'
            value: Output range (float)
        """
        if mode == 'VOLT':
            self.rangev(value)
        elif mode == 'CURR':
            self.rangei(value)
        else:
            raise ValueError("Invalid mode. Choose either 'VOLT' or 'CURR'.")

    def get_output_range(self, mode: Literal['VOLT', 'CURR']) -> float:
        """
        Gets the output range for the specified mode.

        Args:
            mode: 'VOLT' or 'CURR'

        Returns:
            Output range (float)
        """
        if mode == 'VOLT':
            return self.rangev()
        elif mode == 'CURR':
            return self.rangei()
        else:
            raise ValueError("Invalid mode. Choose either 'VOLT' or 'CURR'.")

    def trigger_measurement(self) -> None:
        """
        Triggers a single measurement and updates the corresponding parameter values.

        If the trigger source is set to 'immediate', the trigger is generated internally.
        Otherwise, the trigger must be provided externally or via the bus.
        """
        self.trigger_count(1)  # Ensure we only take one measurement
        if self.trigger_source() == 'immediate':
            self.write(':INITiate')
        else:
            self.write(':TRIGger')

        # Update the values of voltage, current, and resistance parameters
        self.volt.get()
        self.curr.get()
        self.resistance.get()

    def configure_sweep_linear_staircase(
        self,
        start: float,
        stop: float,
        step: float,
        mode: Literal['VOLT', 'CURR'],
        compliance: float,
        points: Optional[int] = None,  # Optional: specify points instead of step
        ranging: Literal["best", "auto", "fixed"] = "best",
        delay: float = 0.0,
    ) -> None:
        """
        Configures a linear staircase sweep.

        Args:
            start: Starting value for the sweep.
            stop: Stopping value for the sweep.
            step: Step size for the sweep.
            mode:  'VOLT' for voltage sweep or 'CURR' for current sweep.
            compliance: Compliance value for the opposite mode.
            points: Number of sweep points (alternative to specifying step).
            ranging: Source ranging mode during sweep ('best', 'auto', or 'fixed').
            delay:  Delay time (in seconds) between each step.
        """

        if step is not None and points is not None:
            raise ValueError("Specify either 'step' or 'points', not both.")

        if points is not None:
            step = (stop - start) / (points - 1)

        if mode == "VOLT":
            self.sweep_start(start)
            self.sweep_stop(stop)
            self.sweep_step(step)
            self.compliancei(compliance)
        elif mode == "CURR":
            self.sweep_start(start)
            self.sweep_stop(stop)
            self.sweep_step(step)
            self.compliancev(compliance)
        else:
            raise ValueError("Invalid mode. Choose either 'VOLT' or 'CURR'.")

        self.sweep_ranging(ranging)
        self.source_delay(delay)

        # If 'points' is provided, calculate and set the number of sweep points
        if points is not None:
            self.sweep_points(points)

    def enable_trigger_link(self, line: int = 2) -> None:
        """
        Enables the Trigger Link output on the specified line.

        Args:
            line: Trigger Link line number (1-4). Default is line 2.
        """
        self.write(f":TRIGger:LINK:LINe {line}")

    def disable_trigger_link(self, line: int = 2) -> None:
        """
        Disables the Trigger Link output on the specified line.

        Args:
            line: Trigger Link line number (1-4). Default is line 2.
        """
        self.write(f":TRIGger:LINK:LINe 0")  # 0 disables all lines

    def read_buffer_data(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Reads the data from the internal buffer.

        Returns:
            Tuple: Two NumPy arrays, one for voltage readings and one for current readings.
        """
        raw_data = self.buffer_read.get()
        data = np.fromstring(raw_data, dtype=float, sep=",")

        voltage_data = data[::2]
        current_data = data[1::2]

        return voltage_data, current_data

    def configure_data_buffer(
        self,
        size: int,
        source_mode: Literal["VOLT", "CURR"],
        elements: Optional[list[str]] = None,
    ) -> None:
        """
        Configure the data buffer to store voltage and current readings.

        Args:
            size: Number of readings to store in the buffer.
            source_mode:  'VOLT' for voltage source or 'CURR' for current source.
            elements:  List of data elements to store, such as 'voltage', 'current', 'resistance', 'time'.
                       Defaults to ['voltage', 'current'].
        """
        self.buffer_size(size)
        if elements is None:
            elements = ["voltage", "current"]
        # Ensure valid elements
        valid_elements = ['voltage', 'current', 'resistance', 'time']
        if not set(elements).issubset(valid_elements):
            raise ValueError(f"Invalid buffer elements. Choose from: {valid_elements}")

        # Construct the element string for the command
        element_str = ",".join(
            [f'"{element.upper()}"' for element in elements]
        )

        self.write(f":TRACe:FEED:CONTrol NEXT")
        self.write(f":FORMat:ELEMents {element_str}")
        self.write(":TRIGger:COUNt {size}")  # Set trigger count to match buffer size

from qcodes import VisaInstrument, Parameter, MultiParameter
from qcodes.utils.validators import Enum, Numbers, Bool
from qcodes.utils.helpers import create_on_off_val_mapping

class Keithley2400Enhanced(Keithley2400):
    """
    Enhanced QCoDeS driver for Keithley 2400 SourceMeter, incorporating best practices
    from the manual for buffering, autoranging, auto delay, NPLC caching, etc.
    """

    def __init__(self, name: str, address: str, **kwargs):
        """
        Initializes the Keithley2400Enhanced driver.

        Args:
            name: Instrument name used internally by QCoDeS.
            address: VISA resource address for the instrument.
            **kwargs: Keyword arguments passed to the base class.
        """
        super().__init__(name, address, **kwargs)

        # Enable 4-wire sense mode by default
        self.sense('remote')

        # Add parameters for enhanced features
        self.add_parameter(
            'auto_delay',
            label='Auto Delay',
            unit='',
            get_cmd='SOUR:DEL:AUTO?',
            set_cmd='SOUR:DEL:AUTO {}',
            val_mapping=create_on_off_val_mapping(on_val='ON', off_val='OFF')
        )

        self.add_parameter(
            'nplc_caching',
            label='NPLC Caching',
            unit='',
            get_cmd='SYST:AZER:CACH?',
            set_cmd='SYST:AZER:CACH {}',
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0)
        )

        self.add_parameter(
            'line_frequency',
            label='Line Frequency',
            unit='Hz',
            get_cmd='SYST:LFR?',
            set_cmd='SYST:LFR {}',
            vals=Enum(50, 60, 'AUTO')  # Allow 'AUTO' for automatic sensing
        )

        self.add_parameter(
            'buffer_points',
            label='Buffer Points',
            unit='',
            get_cmd='TRAC:POIN?',
            set_cmd='TRAC:POIN {}',
            vals=Numbers(1, 2500)
        )

        self.add_parameter(
            'buffer_feed',
            label='Buffer Feed',
            unit='',
            get_cmd='TRAC:FEED?',
            set_cmd='TRAC:FEED {}',
            vals=Enum('SENS', 'CALC1', 'CALC2')
        )

        self.add_parameter(
            'buffer_mode',
            label='Buffer Mode',
            unit='',
            get_cmd='TRAC:FEED:CONT?',
            set_cmd='TRAC:FEED:CONT {}',
            vals=Enum('NEXT', 'NEVER')  # NEXT: Fill and stop, NEVER: Disable
        )

        # Add a multi-parameter for retrieving buffered data
        self.add_parameter(
            'get_buffer_data',
            label='Get Buffer Data',
            unit='',
            get_cmd=self._get_buffer_data,
            names=('voltage', 'current', 'resistance', 'time'),  # Data elements
            parameter_class=MultiParameter
        )

        # Enable auto delay and NPLC caching by default
        self.auto_delay('ON')
        self.nplc_caching(1)

    def _get_buffer_data(self):
        """
        Retrieves and parses the buffered data.

        Returns:
            tuple: A tuple containing arrays for voltage, current, resistance, and time.
        """
        # Read the entire buffer
        raw_data = self.ask('TRAC:DATA?')

        # Split the data into individual readings
        readings = raw_data.split(',')

        # Initialize empty arrays for each data element
        voltage = []
        current = []
        resistance = []
        time = []

        # Parse the data based on the selected buffer feed
        if self.buffer_feed() == 'SENS':
            for i in range(0, len(readings), 5):  # 5 elements per reading (V, I, R, T, Status)
                voltage.append(float(readings[i]))
                current.append(float(readings[i+1]))
                resistance.append(float(readings[i+2]))
                time.append(float(readings[i+3]))
        elif self.buffer_feed() in ('CALC1', 'CALC2'):
            for i in range(0, len(readings), 2):  # 2 elements per reading (Value, Time)
                if self.buffer_feed() == 'CALC1':
                    voltage.append(float(readings[i]))  # Assuming CALC1 result is voltage
                elif self.buffer_feed() == 'CALC2':
                    resistance.append(float(readings[i]))  # Assuming CALC2 result is resistance
                time.append(float(readings[i+1]))

        # Convert lists to NumPy arrays
        return np.array(voltage), np.array(current), np.array(resistance), np.array(time)

    def enable_buffer(self, points: int, feed: str, mode: str):
        """
        Configures and enables the instrument's data buffer.

        Args:
            points: Number of readings to store in the buffer.
            feed:  Source of readings for the buffer ('SENS', 'CALC1', 'CALC2').
            mode: Buffer control mode ('NEXT', 'NEVER').
        """
        self.buffer_points(points)
        self.buffer_feed(feed)
        self.buffer_mode(mode)

    def clear_buffer(self):
        """
        Clears the instrument's data buffer.
        """
        self.write('TRAC:CLE')
