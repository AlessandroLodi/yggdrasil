from qcodes import VisaInstrument, validators as vals
from qcodes.utils.helpers import create_on_off_val_mapping

class Keithley6517A(VisaInstrument):
    """
    QCoDeS driver for the Keithley 6517A Electrometer
    """

    def __init__(self, name, address, **kwargs):
        super().__init__(name, address, terminator='\n', **kwargs)

        # Add parameters
        self.add_parameter('function',
                           label='Measurement function',
                           get_cmd=':SENS:FUNC?',
                           set_cmd=':SENS:FUNC "{}"',
                           val_mapping={'voltage': 'VOLT', 'current': 'CURR',
                                        'resistance': 'RES', 'charge': 'CHAR'})

        self.add_parameter('range',
                           label='Measurement range',
                           get_cmd=self._get_range,
                           set_cmd=self._set_range,
                           vals=vals.Numbers())

        self.add_parameter('nplc',
                           label='Integration time',
                           unit='NPLC',
                           get_cmd=self._get_nplc,
                           set_cmd=self._set_nplc,
                           vals=vals.Numbers(0.01, 10))

        self.add_parameter('zero_check',
                           label='Zero check',
                           get_cmd=':SYST:ZCH?',
                           set_cmd=':SYST:ZCH {}',
                           val_mapping=create_on_off_val_mapping(on_val='1', off_val='0'))

        self.add_parameter('zero_correct',
                           label='Zero correct',
                           get_cmd=':SYST:ZCOR?',
                           set_cmd=':SYST:ZCOR {}',
                           val_mapping=create_on_off_val_mapping(on_val='1', off_val='0'))

        self.add_parameter('voltage_source',
                           label='Voltage source',
                           unit='V',
                           get_cmd=':SOUR:VOLT?',
                           set_cmd=':SOUR:VOLT {}',
                           vals=vals.Numbers(-1000, 1000))

        self.add_parameter('voltage_source_enable',
                           label='Voltage source enable',
                           get_cmd=':SOUR:VOLT:STAT?',
                           set_cmd=':SOUR:VOLT:STAT {}',
                           val_mapping=create_on_off_val_mapping(on_val='1', off_val='0'))

        self.add_parameter('read',
                           label='Measurement value',
                           get_cmd=':READ?',
                           get_parser=float)

        # Connect to instrument
        self.connect_message()

    def _get_range(self):
        func = self.function()
        return float(self.ask(f':SENS:{func}:RANG?'))

    def _set_range(self, value):
        func = self.function()
        self.write(f':SENS:{func}:RANG {value}')

    def _get_nplc(self):
        func = self.function()
        return float(self.ask(f':SENS:{func}:NPLC?'))

    def _set_nplc(self, value):
        func = self.function()
        self.write(f':SENS:{func}:NPLC {value}')

    def reset(self):
        """Reset the instrument to default settings."""
        self.write('*RST')

    def get_idn(self):
        """Get instrument identification."""
        return self.ask('*IDN?')

# Usage example:
if __name__ == "__main__":
    from qcodes import Station

    # Create a station
    station = Station()

    # Create the instrument
    k6517a = Keithley6517A('electrometer', 'GPIB0::27::INSTR')

    # Add the instrument to the station
    station.add_component(k6517a)

    # Now you can use the instrument within the QCoDeS framework
    print(k6517a.get_idn())
    k6517a.function('voltage')
    k6517a.range(20)
    k6517a.nplc(1)
    k6517a.zero_check('on')
    k6517a.zero_correct('on')
    k6517a.zero_check('off')
    
    voltage = k6517a.read()
    print(f"Measured voltage: {voltage} V")

    # Close the instrument connection
    k6517a.close()