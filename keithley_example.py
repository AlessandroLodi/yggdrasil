import pyvisa

rm = pyvisa.ResourceManager()
print(rm.list_resources())

# Create an instance of the Keithley 2400 driver
# Replace 'GPIB0::25::INSTR' with the actual VISA address of your instrument
# k2400 = Keithley2400('k2400', 'GPIB0::25::INSTR')

# # Set the source mode to voltage
# k2400.source_mode('voltage')

# # Set the voltage to 1V
# k2400.source_voltage(1)

# # Set the current compliance to 10mA
# k2400.current_range(0.01)

# # Enable the output
# k2400.output_enabled(True)

# # Measure the current
# current = k2400.current()
# print(f"Measured current: {current} A")

# # Disable the output
# k2400.output_enabled(False)

# # Close the connection when done
# k2400.close()
