# import pyvisa
# import numpy as np
# from time import sleep, time
# from datetime import datetime

# from qcodes import Station, Parameter
# from qcodes.dataset import Measurement
# from instrument_drivers import Keithley_2400
# from instrument_drivers import Keithley_6517A
# from qcodes.utils.plotting import QtPlot

import pyvisa
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui
from time import sleep
from datetime import datetime

import time

from qcodes import Station, Parameter
from qcodes.dataset import Measurement

from instrument_drivers.Keithley_6517A import Keithley_6517A
from instrument_drivers.Keithley_2400 import Keithley2400Enhanced


# --- Constants ---
K2400_ADDRESS = 'GPIB0::1::INSTR'
K6517A_ADDRESS = 'GPIB0::26::INSTR'
K2400_OUTPUT_VOLTAGE = 5  # Set fixed output voltage for K2400
K6517A_OUTPUT_VOLTAGE = 30  # Set fixed output voltage for K6517A
MEASUREMENT_DURATION = 60  # Measurement duration in seconds
SAMPLING_INTERVAL = 1  # Time interval between measurements in seconds
DATA_FILE = 'current_monitoring.csv'

# --- Helper Functions ---
def timestamp():
    """Return current timestamp as a formatted string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# --- Plotting Class --- (Reusing from previous example)
# --- Plotting Class ---
class LivePlot:
    """Modular class for live plotting using PyQtGraph."""

    def __init__(self, window_title: str = 'Live Plot'):
        self.app = QtGui.QApplication([])  # Initialize PyQt application
        self.win = pg.GraphicsWindow(title=window_title)
        self.win.resize(1000, 600)
        self.win.setWindowTitle(window_title)

        # Create two plots for two data sets
        self.plot1 = self.win.addPlot(title='K2400 Current vs. Voltage')
        self.plot1.setLabel('left', 'Current', units='A')
        self.plot1.setLabel('bottom', 'Voltage', units='V')
        self.curve1 = self.plot1.plot(pen='r', symbol='o')

        self.win.nextRow()  # Move to the next row for a new plot

        self.plot2 = self.win.addPlot(title='K6517A Current vs. Voltage')
        self.plot2.setLabel('left', 'Current', units='A')
        self.plot2.setLabel('bottom', 'Voltage', units='V')
        self.curve2 = self.plot2.plot(pen='b', symbol='x')

        self.voltage_data = []
        self.k2400_current_data = []
        self.k6517a_current_data = []

    def add_data(self, voltage, current_k2400, current_k6517a):
        """Adds new data points to the plot."""
        self.voltage_data.append(voltage)
        self.k2400_current_data.append(current_k2400)
        self.k6517a_current_data.append(current_k6517a)

        self.curve1.setData(self.voltage_data, self.k2400_current_data)
        self.curve2.setData(self.voltage_data, self.k6517a_current_data)

        pg.QtGui.QApplication.processEvents()

    def close(self):
        """Closes the plot window."""
        self.win.close()
        self.app.quit()

# --- Measurement Class ---
class CurrentMonitor(Measurement):
    """
    Monitors current from both Keithley 2400 and 6517A while they
    output fixed voltages. Provides live plotting of the data.
    """

    def __init__(self, station: Station, data_file: str = DATA_FILE):
        super().__init__(exp=None, station=station)
        self.k2400 = self.station.components['k2400']
        self.k6517a = self.station.components['k6517a']
        self.time_param = Parameter(name='time', label='Time', unit='s')
        self.data_file = data_file
        self.plot = LivePlot(window_title='Current Monitoring')

    def prepare(self):
        """Prepare instruments and plot for measurement."""
        # Configure Keithley 2400
        self.k2400.source('voltage')
        self.k2400.source_level(K2400_OUTPUT_VOLTAGE)
        self.k2400.output(True)

        # Configure Keithley 6517A
        self.k6517a.sense_function('current')
        self.k6517a.res_auto_vsource(0)
        self.k6517a.res_vsource_range(1000)
        self.k6517a.res_vsource_level(K6517A_OUTPUT_VOLTAGE)
        self.k6517a.res_vsource_operate(1)

        # Register parameters
        self.register_parameter(self.time_param)
        self.register_parameter(self.k2400.current, setpoints=(self.time_param,))
        self.register_parameter(self.k6517a.current, setpoints=(self.time_param,))

        # Add curves to the live plot
        self.plot.add_curve(self.time_param, self.k2400.current, 
                           name='K2400 Current', symbol='o')
        self.plot.add_curve(self.time_param, self.k6517a.current, 
                           name='K6517A Current', symbol='x')

        # Print measurement info
        print(f"--- Current Monitoring ---")
        print(f"Timestamp: {timestamp()}")
        print(f"K2400 outputting {K2400_OUTPUT_VOLTAGE} V")
        print(f"K6517A outputting {K6517A_OUTPUT_VOLTAGE} V")

    def measure_and_save(self):
        """Measures currents, saves data, and updates the plot."""
        start_time = time()
        elapsed_time = 0

        while elapsed_time <= MEASUREMENT_DURATION:
            current_k2400 = self.k2400.current()
            current_k6517a = self.k6517a.current()
            self.time_param(elapsed_time)

            self.data.add_result((self.time_param, elapsed_time),
                                 (self.k2400.current, current_k2400),
                                 (self.k6517a.current, current_k6517a))

            # Append data to file
            with open(self.data_file, 'a') as f:
                f.write(f"{timestamp()},{elapsed_time},{current_k2400},{current_k6517a}\n")

            # Update the live plot
            self.plot.update()

            sleep(SAMPLING_INTERVAL)
            elapsed_time = time() - start_time

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
    experiment = CurrentMonitor(station)

    # Run the experiment
    experiment.run() 