import pytest

from qcodes.instrument_drivers.mock_instruments import DummyInstrument

import sys
import os

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(project_root)

# Now import the module
from instrument_drivers.Keithley_6517A import Keithley_6517A

@pytest.fixture(scope="function")
def mock_keithley():
    inst = DummyInstrument(name="mock_keithley")
    yield inst
    inst.close()

@pytest.fixture(scope="function")
def keithley(mock_keithley):
    keithley_instance = Keithley_6517A(name="keithley", address="GPIB::15::INSTR", visa_handle=mock_keithley)
    return keithley_instance

def test_idn(keithley):
    idn = keithley.get_idn()
    assert isinstance(idn, dict)
    assert "vendor" in idn
    assert "model" in idn
    assert "serial" in idn
    assert "firmware" in idn

def test_sense_function(keithley):
    keithley.sense_function("voltage")
    assert keithley.sense_function() == "voltage"
    keithley.sense_function("current")
    assert keithley.sense_function() == "current"

def test_zerocheck(keithley):
    keithley.zerocheck(True)
    assert keithley.zerocheck() == True
    keithley.zerocheck(False)
    assert keithley.zerocheck() == False

def test_auto_meas_range(keithley):
    keithley.auto_meas_range(True)
    assert keithley.auto_meas_range() == True
    keithley.auto_meas_range(False)
    assert keithley.auto_meas_range() == False

def test_meas_range(keithley):
    keithley.sense_function("voltage")
    keithley.auto_meas_range(False)
    keithley.meas_range(10)
    assert keithley.meas_range() == 10

def test_stsweep_setup(keithley):
    keithley.stsweep_setup(0, 1, 10, 0.1)
    assert keithley.tseq_type() == "stsweep"
    assert keithley.tseq_stsweep_start() == 0
    assert keithley.tseq_stsweep_step() == 1
    assert keithley.tseq_stsweep_stop() == 10
    assert keithley.tseq_stsweep_stime() == 0.1

def test_get_data(keithley):
    # This test assumes that get_data returns a dictionary with 'reading' key
    data = keithley.get_data(element='reading', tseq=False)
    assert isinstance(data, (float, int))

if __name__ == "__main__":
    pytest.main([__file__])
