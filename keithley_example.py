import pyvisa
from qcodes.instrument_drivers.Keithley.Keithley_2400 import Keithley2400
rm = pyvisa.ResourceManager()

print(rm.list_resources())

# Initialize the Keithley2400
k2400 = Keithley2400('k2400', 'GPIB0::1::INSTR')

# Set the voltage to 1V
k2400.volt(1)

# Set the current compliance to 10mA
k2400.compliancei(0.01)

# Set the mode to voltage source
k2400.mode('VOLT')

# Enable the output
k2400.output(True)

# Measure the current
current = k2400.curr()
print(f"Measured current: {current} A")

# Disable the output
k2400.output(False)

# Close the instrument connection
k2400.close()
