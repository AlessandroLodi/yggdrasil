import pyvisa

class Keithley6517A:
    def __init__(self, resource_name):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = 5000  # Set timeout to 5 seconds
        self.inst.clear()  # Clear the instrument buffer
        
    def __del__(self):
        if hasattr(self, 'inst'):
            self.inst.close()
        if hasattr(self, 'rm'):
            self.rm.close()

    def reset(self):
        """Reset the instrument to default settings."""
        self.inst.write("*RST")

    def identify(self):
        """Query the instrument identification."""
        return self.inst.query("*IDN?")

    def set_measure_function(self, function):
        """Set the measurement function."""
        valid_functions = ['VOLT', 'CURR', 'RES', 'CHAR']
        if function.upper() not in valid_functions:
            raise ValueError(f"Invalid function. Choose from {valid_functions}")
        self.inst.write(f":SENS:FUNC '{function}'")

    def get_measure_function(self):
        """Get the current measurement function."""
        return self.inst.query(":SENS:FUNC?")

    def measure(self):
        """Perform a measurement and return the result."""
        return float(self.inst.query(":READ?"))

    def set_range(self, range_value):
        """Set the measurement range."""
        current_function = self.get_measure_function().strip("'")
        self.inst.write(f":SENS:{current_function}:RANG {range_value}")

    def set_integration_time(self, nplc):
        """Set the integration time in number of power line cycles (NPLC)."""
        current_function = self.get_measure_function().strip("'")
        self.inst.write(f":SENS:{current_function}:NPLC {nplc}")

    def enable_zero_check(self, state=True):
        """Enable or disable zero check."""
        self.inst.write(f":SYST:ZCH {'ON' if state else 'OFF'}")

    def enable_zero_correct(self, state=True):
        """Enable or disable zero correct."""
        self.inst.write(f":SYST:ZCOR {'ON' if state else 'OFF'}")

    def set_voltage_source(self, voltage):
        """Set the voltage source value."""
        self.inst.write(f":SOUR:VOLT {voltage}")

    def enable_voltage_source(self, state=True):
        """Enable or disable the voltage source."""
        self.inst.write(f":SOUR:VOLT:STAT {'ON' if state else 'OFF'}")

# Example usage:
if __name__ == "__main__":
    # Replace 'GPIB0::27::INSTR' with your actual VISA resource string
    electrometer = Keithley6517A('GPIB0::27::INSTR')
    
    print(electrometer.identify())
    
    electrometer.set_measure_function('VOLT')
    electrometer.set_range(20)  # 20V range
    electrometer.set_integration_time(1)  # 1 NPLC
    
    electrometer.enable_zero_check(True)
    electrometer.enable_zero_correct(True)
    electrometer.enable_zero_check(False)
    
    voltage = electrometer.measure()
    print(f"Measured voltage: {voltage} V")