import os
import json
import numpy as np
import pandas as pd
from time import localtime, strftime, sleep
from functools import partial
from tqdm import tqdm

import qcodes
from qcodes import Parameter, ParamSpec
from qcodes.utils.validators import Numbers
from qcodes.instrument.base import Instrument
from qcodes.dataset import Measurement
from qcodes.dataset.data_set import DataSet

from .configuration.config import ConfigInstrument
# from qcodes.instrument_drivers.tektronix.Keithley_6517A import Keithley_6517A

# Configure tqdm for better progress bars
tqdm = partial(tqdm, position=0, leave=True)

class StaircaseSweep(Measurement):
    """
    Conducts staircase sweep measurement.
    
    Args:
        high_res: bool, whether to use high resistance mode
        experiment: Experiment object
        station: Station object that holds all the instruments
        sample: Sample object
        filepath: str, filepath to store all related files
    """
    def __init__(self, high_res: bool, experiment, station, sample, name=""):
        super().__init__(experiment, station, name)
        self.high_res = high_res
        self.sample = sample
        self.filepath = self.sample.file_path
        self.instruments = self.station.components
        self.instr_config = ConfigInstrument(path=self.filepath)
        self.k6517a = None
        self._mode = ""

        if self.high_res:
            self._setup_high_res_mode()

        self.add_before_run(self._ensure_door_closed, args=())
        self.add_after_run(self._close_k6517a_output, args=())

    def _setup_high_res_mode(self):
        for name, instr in self.instruments.items():
            if isinstance(instr, Keithley_6517A):
                self.k6517a = instr
                self.k6517a_name = name
                break
        if not self.k6517a:
            raise RuntimeError(f"Please add Keithley 6517A to the station. Current instruments: {self.instruments}")

    def set_parameters(self, start_v, stop_v, step_v, npts_per_step, time_step, num_sweep, relax_time=0):
        """
        Set parameters for staircase sweep measurement.
        
        Args:
            start_v: float, start voltage
            stop_v: float, stop voltage
            step_v: float, step voltage
            npts_per_step: int, number of data points per step
            time_step: float, time of each step
            num_sweep: int, number of sweeps
            relax_time: float, relax time after each sweep
        """
        self._validate_parameters(start_v, stop_v, step_v)
        self.max_v = max(abs(start_v), abs(stop_v))
        self.sweep_arguments = locals()
        self._generate_measurement_name()

    def _validate_parameters(self, start_v, stop_v, step_v):
        Numbers(0, 1000).validate(abs(start_v))
        Numbers(0, 1000).validate(abs(stop_v))
        Numbers(0, abs(start_v - stop_v)).validate(abs(step_v))

    def _ensure_door_closed(self):
        """Ensure the enclosure door is closed for hazardous voltage."""
        if self.max_v >= 36 and not self.k6517a.interlock():
            raise RuntimeError("Please close the cabinet door before using hazardous voltage!")
                        
    def _close_k6517a_output(self):
        try:
            self.k6517a.operate(False)
        except:
            pass

    def print_info(self):
        """Print information before starting the sweep."""
        print(f"Current working directory: {os.getcwd()}")
        print(f"Database file path: {qcodes.config.core.db_location}")
        print(f"Experiment name: {self.experiment.name}")
        print(f"High resistance mode: {self.high_res}")
        print(f"Instruments: {self.instruments}")
        print(f"Sample name: {self.sample.full_name}")
        print(f"Measurement name: {self.name}")

    def log_data(self, dataset: DataSet, data_dict: dict):
        """Log data to a CSV file."""
        csvname = f"Run_id {dataset.captured_run_id} {dataset.name}.csv"
        csvpath = os.path.join(self.filepath, csvname)
        with open(csvpath, 'a', encoding='utf-8') as f:
            f.write(self._generate_log_header(dataset))
            for k, v in self.sweep_arguments.items():
                f.write(f"\t{k},\t{v}\n")
            f.write(f"\n\tNominal sweep rate, \t{self.sweep_rate}\n\tReal sweep rate, \t{self._calculate_real_sweep_rate(dataset)}\n")
            f.write(f"\nDataset run_id, \t{dataset.captured_run_id}\nDataset guid, \t{dataset.guid}\n\nData:\n")
        pd.DataFrame(data_dict).to_csv(csvpath, mode='a', sep=',')

    def _generate_log_header(self, dataset):
        return f"""
Time, \t{dataset.run_timestamp()}
Database file path, \t{qcodes.config.core.db_location}
Experiment, \t{self.experiment.name}
Staircase Sweep mode, \t{self._mode}
High resistance mode, \t{self.high_res}
Measurement name, \t{self.name}

Sample:
\tSample full name, {self.sample.full_name}
\tContact method, {self.sample.contact_method}
\tProbe distance, {self.sample.probe_distance} mm

Parameters:
"""

    def log_run_id(self, dataset: DataSet):
        """Record the sample and measurement name and their run-id's."""
        filename = f"{self.sample.full_name}_runid.log"
        filepath = os.path.join(self.filepath, filename)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"{dataset.captured_run_id}:{self._mode}, {self.name}\n")

    def log_6517a(self):
        """Record the Keithley 6517A configuration snapshot."""
        k6517a_log = f"{self.k6517a.name}_snapshot_readable.log"
        self.instr_config.write_file(path=os.path.join(self.filepath, k6517a_log),
                                     from_print=True,
                                     print_func=self.k6517a.print_readable_snapshot)

    def _generate_measurement_name(self):
        params = self.sweep_arguments
        sr = params["step_v"] / params["time_step"]
        self.sweep_rate = f"{sr:.2f} V/s"
        sr_str = str(sr).replace('.', '-') if sr % 1 != 0 else str(int(sr))
        sweep_rate_str = f"{sr_str}V-s"
        volt_range = f"{params['start_v']}to{params['stop_v']}V"
        num_sweep = f"{params['num_sweep']} sweeps"
        relax = f"relax {int(params['relax_time']/60)}mins" if params["relax_time"] else ''
        self.name = "__".join([self.sample.full_name, self.experiment.name,
                               self.sample.contact_method, sweep_rate_str, volt_range,
                               num_sweep, relax]).strip('_')

    @staticmethod
    def _calculate_real_sweep_rate(dataset):
        data = dataset.get_parameter_data()
        voltage, time = None, None
        for key, value in data.items():
            if 'current' in key:
                voltage = value['voltage']
            if 'time' in key:
                time = list(value.values())[0]
        sr = np.array([np.polyfit(time[i], voltage[i], 1)[0] for i in range(len(voltage))])
        return f"{np.abs(sr).mean():.2f} V/s"

class TSEQStaircaseSweep(StaircaseSweep):
    """
    Built-in function of Keithley 6517A.
    """
    def __init__(self, high_res: bool, experiment, station, sample, name=""):
        super().__init__(high_res, experiment, station, sample, name)
        self._mode = "Test Sequence Staircase Sweep"
        self._register_parameters()

    def _register_parameters(self):
        self.register_parameter(self.k6517a.tseq_voltage)
        self.register_parameter(self.k6517a.tseq_current)
        self.register_parameter(self.k6517a.tseq_time)

    def configure_k6517a(self, sense_function='current', auto_meas_range=True,
                         elements_for_data=('reading', 'units', 'timestamp', 'vsource'),
                         timestamp_format='relative', current_damping=True):
        """Configure Keithley 6517A for the staircase sweep measurement."""
        self.k6517a.zerocheck(1)
        self.k6517a.datetime_calibrate()
        self.k6517a.preset()
        self.k6517a.sense_function(sense_function)
        self.k6517a.current_damping(current_damping)
        self.k6517a.meter_connect(1)
        self.k6517a.elements_for_data(*elements_for_data)
        self.k6517a.auto_meas_range(auto_meas_range)
        self.k6517a.timestamp(timestamp_format)
        self.k6517a.tseq_type('stsweep')
        self.k6517a.tseq_trigger_source('immediate')
        self.log_6517a()

    def start_sweep(self):
        """Start the measuring."""
        self.print_info()
        self.data_dict = {}

        start_voltage = self.sweep_arguments["start_v"]
        stop_voltage = self.sweep_arguments["stop_v"]
        step_voltage = self.sweep_arguments["step_v"]
        step_time = self.sweep_arguments["time_step"]

        self._do_sweep(start_voltage, step_voltage, stop_voltage, step_time)

    def _do_sweep(self, start, step, stop, stime):
        with self.run() as datasaver:
            for s in range(self.sweep_arguments['num_sweep']):
                try:
                    print(f"\n Start sweep No. {s+1}")

                    self.k6517a.tseq_stsweep_start(start)
                    self.k6517a.tseq_stsweep_step(step)
                    self.k6517a.tseq_stsweep_stop(stop)
                    self.k6517a.tseq_stsweep_stime(stime)

                    self.k6517a.tseq_arm()

                    t = 0
                    while t < ((stop-start)//step+1)*(0.8+stime)+10:
                        t += 1
                        sleep(1)
                        print(self.k6517a.read_display_top())

                    voltage = self.k6517a.tseq_voltage()
                    current = self.k6517a.tseq_current()
                    time = self.k6517a.tseq_time()
                    current[current > 1] = np.nan

                    datasaver.add_result((self.k6517a.tseq_voltage, voltage),
                                         (self.k6517a.tseq_current, current),
                                         (self.k6517a.tseq_time, time))
                    self.data_dict.update({
                        f"Current-{s+1}": current,
                        f"Voltage-{s+1}": voltage,
                        f"Time-{s+1}": time
                    })

                    self.k6517a.zerocheck(1)
                    start, step, stop = stop, -step, start

                except KeyboardInterrupt:
                    self.k6517a.tseq_abort()
                    self.k6517a.operate(0)
                    print("Stopped the test sequence")
                    break
                self.k6517a.operate(0)

            self.dataset = datasaver.dataset
            self.log_data(self.dataset, self.data_dict)
            self.log_run_id(self.dataset)

class CustomizedStaircaseSweep(StaircaseSweep):
    """
    Customized staircase sweep, compared to the built-in test sequence.
    """
    def __init__(self, high_res: bool, experiment, station, sample, name=""):
        super().__init__(high_res, experiment, station, sample, name)
        self._mode = "Customized Staircase Sweep"
        self._register_parameters()

    def _register_parameters(self):
        self.sweep_voltage = Parameter(name='voltage', label='Voltage', unit='V')
        self.sweep_time = Parameter(name='time', label='Time', unit='s')
        self.sweep_current = Parameter(name='current', label='Current', unit='A')
        self.register_parameter(self.sweep_voltage, paramtype='array')
        self.register_parameter(self.sweep_time, paramtype='array')
        self.register_parameter(self.sweep_current, paramtype='array', setpoints=(self.sweep_voltage,))

    def configure_k6517a(self, sense_function='current', auto_meas_range=True,
                         elements_for_data=('reading', 'units', 'timestamp', 'vsource'),
                         timestamp_format='relative', current_damping=True):
        """Configure Keithley 6517A for the staircase sweep measurement."""
        self.k6517a.zerocheck(1)
        self.k6517a.datetime_calibrate()
        self.k6517a.preset()
        self.k6517a.sense_function(sense_function)
        self.k6517a.current_damping(current_damping)
        self.k6517a.meter_connect(1)
        self.k6517a.res_auto_vsource(0)
        vs_range = 1000 if self.max_v > 100 else 100
        self.k6517a.res_vsource_range(vs_range)
        self.k6517a.elements_for_data(*elements_for_data)
        self.k6517a.auto_meas_range(auto_meas_range)
        self._auto_range = auto_meas_range
        self.k6517a.timestamp(timestamp_format)
        self.k6517a.zerocheck(0)
        self.log_6517a()

    def start_sweep(self):
        """Start the measuring."""
        self.print_info()
        self.current = np.array([])
        self.time = np.array([])
        self.voltage = np.array([])
        self.data_dict = {}

        start_voltage = self.sweep_arguments["start_v"]
        stop_voltage = self.sweep_arguments["stop_v"]
        step_voltage = self.sweep_arguments["step_v"]

        self._do_sweep(start_voltage, step_voltage, stop_voltage)
        self.k6517a.res_vsource_operate(0)

    def _do_sweep(self, start, step, stop):
        with self.run() as datasaver:
            for i in range(self.sweep_arguments['num_sweep']):
                print(f"\n Start sweep No. {i+1}")
                current, time, voltage = self._single_run(start, step, stop)
                if self.sweep_arguments["relax_time"] != 0:
                    self.k6517a.res_vsource_operate(0)

                self.data_dict.update({
                    f"Current-{i+1}": current,
                    f"Voltage-{i+1}": voltage,
                    f"Time-{i+1}": time
                })

                start, step, stop = stop, -step, start

                datasaver.add_result((self.sweep_current, current),
                                     (self.sweep_voltage, voltage),
                                     (self.sweep_time, time))
            self.dataset = datasaver.dataset
            self.log_data(self.dataset, self.data_dict)
            self.log_run_id(self.dataset)

    def _single_run(self, start, step, stop):
        """Execute a single sweep."""
        _curr, _volt, _time = [], [], []
        flag142pA = 0
        flag142pAidx = []

        if abs(stop) > 100 and float(self.k6517a.res_vsource_range()) <= 100:
            self.k6517a.res_vsource_range(1000)

        self.k6517a.res_vsource_operate(1)
        self._meas_range = float(self.k6517a.meas_range())

        for v in tqdm(np.arange(start, stop, step)):
            self.k6517a.res_vsource_level(v)
            c, t = self._read_current_time()
            absr = np.abs(c[0])

            self._adjust_meas_range(absr, v, step, flag142pA, flag142pAidx)

            _curr.extend(c)
            _volt.extend([v]*len(c))
            _time.extend(t)

        current, voltage, time = map(np.array, (_curr, _volt, _time))
        current[flag142pAidx] = np.nan
        current[current > 1] = np.nan

        return current, time, voltage

    def _read_current_time(self):
        """Read current and time values."""
        c, t = [], []
        for _ in range(self.sweep_arguments["npts_per_step"]):
            sleep(self.sweep_arguments["time_step"])
            dat = self.k6517a.get_data(tseq=False)
            c.append(dat['reading'][0])
            t.append(dat['timestamp'][0])
        return c, t

    def _adjust_meas_range(self, absr, v, step, flag142pA, flag142pAidx):
        """Adjust measurement range based on current values."""
        mr_now = self._meas_range
        flr, cer = self._calculate_range_bounds(absr)

        if self._auto_range == False:
            if mr_now > cer:
                self.k6517a.meas_range(cer)
                self._meas_range = cer
            elif mr_now <= flr:
                self._handle_range_overflow(absr, mr_now)

            if round(mr_now*10**10) == 2 and 1.4e-10 <= absr <= 1.44e-10:
                flag142pA += 1
                flag142pAidx.append(int((v - start) / step))
                if flag142pA >= 5:
                    self.k6517a.meas_range(2e-9)
                    self._meas_range = 2e-9

    def _calculate_range_bounds(self, absr):
        flr = 2 * 10**(np.floor(np.log10(absr/2)))
        cer = 2 * 10**(np.ceil(np.log10(absr/2)))
        if flr < 2e-15:
            flr = 2e-13
        if cer < 2e-15:
            cer = 2e-11
        if cer == 2e-9 and absr > 0.8e-9:
            cer *= 10
        return flr, cer

    def _handle_range_overflow(self, absr, mr_now):
        if 0 < absr < 1:
            self.k6517a.meas_range(mr_now)
            self._meas_range = mr_now
        elif absr > 1 and mr_now <= 2e-3:
            self.k6517a.meas_range(mr_now*10)
            self._meas_range = mr_now*10