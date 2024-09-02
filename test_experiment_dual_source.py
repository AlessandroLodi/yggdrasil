import pyvisa
import numpy as np
from time import sleep
from datetime import datetime

from qcodes import Station, ManualParameter
from qcodes.dataset import Measurement
from qcodes.sweep import sweep, measure

from instrument_drivers.Keithley_6517A import Keithley_6517A
from instrument_drivers.Keithley_2400 import Keithley2400Enhanced
from qcodes.plots.pyqtgraph import QtPlot

# --- Constants ---
K2400_ADDRESS = 'GPIB0::1::INSTR'
K6517A_ADDRESS = 'GPIB0::22::INSTR'
SWEEP_VOLTAGE_RANGE = (-10, 10)
SWEEP_VOLTAGE_POINTS = 101
K6517A_VOLTAGE = 50 
K2400_COMPLIANCE_CURRENT = 0.1
DATA_FILE = 'sweep_data.csv'

# --- Helper Functions ---
def timestamp():
    """Return current timestamp as a formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- Plotting Class ---
class LivePlot:
    """Modular class for live plotting using QtPlot."""

    def __init__(self, window_title: str = 'Live Plot'):
        self.plot = QtPlot(window_title=window_title)
        self.curves = {}  # Store curves (name: QtPlot curve)

    def add_curve(self, x_param: Parameter, y_param: Parameter, 
                  name: str, symbol: str = 'o'):
        """
        Adds a curve to the plot.

        Args:
            x_param: Parameter for the x-axis.
            y_param: Parameter for the y-axis.
            name:  Name of the curve (for legend).
            symbol: Symbol to use for data points ('o', 'x', '+', etc.).
        """
        curve = self.plot.add_graph(x_param, y_param, name=name, symbol=symbol)
        self.curves[name] = curve

    def update(self):
        """Updates the plot with the latest data."""
        self.plot.update()

    def close(self):
        """Closes the plot window."""
        self.plot.close()

# --- Measurement Class ---
class DualSourceMeasure(Measurement):
    """
    Performs a synchronized voltage sweep on a Keithley 2400 
    while simultaneously measuring current from a Keithley 6517A
    with a constant voltage output. Provides live plotting of the data.
    """

    def __init__(self, station: Station, data_file: str = DATA_FILE):
        super().__init__(exp=None, station=station)

        self.k2400 = self.station.components['k2400']
        self.k6517a = self.station.components['k6517a']
        self.sweep_voltage = ManualParameter(name='sweep_voltage', 
                                             label='Sweep Voltage', 
                                             unit='V',
                                             initial_value=0) 

        self.data_file = data_file
        self.plot = LivePlot(window_title='Dual Source Measure')

    def prepare(self):
        """Prepare instruments and plot for measurement."""
        # Configure Keithley 2400
        self.k2400.source('voltage')
        self.k2400.compliance.current(K2400_COMPLIANCE_CURRENT)

        # Configure Keithley 6517A
        self.k6517a.sense_function('current')
        self.k6517a.res_auto_vsource(0)
        self.k6517a.res_vsource_range(1000)
        self.k6517a.res_vsource_level(K6517A_VOLTAGE)
        self.k6517a.res_vsource_operate(1)

        # Register parameters
        self.register_parameter(self.sweep_voltage)
        self.register_parameter(self.k2400.current, setpoints=(self.sweep_voltage,))
        self.register_parameter(self.k6517a.current, setpoints=(self.sweep_voltage,))

        # Add curves to the live plot
        self.plot.add_curve(self.sweep_voltage, self.k2400.current, 
                           name='K2400 Current', symbol='o')
        self.plot.add_curve(self.sweep_voltage, self.k6517a.current, 
                           name='K6517A Current', symbol='x')

        # Print measurement info
        print(f"--- Dual Source Measure ---")
        print(f"Timestamp: {timestamp()}")
        print(f"Sweeping K2400 voltage from {SWEEP_VOLTAGE_RANGE[0]} to {SWEEP_VOLTAGE_RANGE[1]} V")
        print(f"K6517A outputting {K6517A_VOLTAGE} V")

    def measure_and_save(self, voltage: float):
        """
        Sets the voltage on K2400, measures currents, saves data, and updates plot.

        Args:
            voltage: Voltage setpoint for the Keithley 2400.
        """
        self.k2400.source_level(voltage)
        sleep(0.1)  # Optional short delay for settling
        current_k2400 = self.k2400.current()
        current_k6517a = self.k6517a.current()

        self.data.add_result((self.sweep_voltage, voltage),
                             (self.k2400.current, current_k2400),
                             (self.k6517a.current, current_k6517a))

        # Append data to file
        with open(self.data_file, 'a') as f:
            f.write(f"{timestamp()},{voltage},{current_k2400},{current_k6517a}\n")

        # Update the live plot
        self.plot.update()

    def finish(self):
        """Disable outputs and close plot."""
        self.k2400.output(False)
        self.k6517a.res_vsource_operate(0)
        self.plot.close()

# --- Main Experiment ---
if __name__ == "__main__":
    # Initialize PyVISA
    rm = pyvisa.ResourceManager()

    # Connect to instruments
    k2400 = Keithley2400Enhanced('k2400', K2400_ADDRESS)
    k6517a = Keithley_6517A('k6517a', K6517A_ADDRESS)

    # Create a station
    station = Station(k2400, k6517a)

    # Set up the experiment
    experiment = DualSourceMeasure(station)
    experiment.sweep_voltage.set_range(*SWEEP_VOLTAGE_RANGE)

    # Perform the sweep and live plot
    with experiment.run() as datasaver:
        for voltage in sweep(experiment.sweep_voltage, 
                          np.linspace(*SWEEP_VOLTAGE_RANGE, SWEEP_VOLTAGE_POINTS)):
            experiment.measure_and_save(voltage) 

    # Print the final dataset
    print(datasaver.dataset)