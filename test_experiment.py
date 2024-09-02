import qcodes as qc
from qcodes.station import Station
from instrument_drivers.Keithley_6517A import Keithley_6517A
from instrument_drivers.Keithley_2400 import Keithley2400
from measurement import StaircaseSweep

# Initialize the instruments
k6517a = Keithley_6517A('k6517a', 'GPIB0::27::INSTR')
k2400 = Keithley2400('k2400', 'GPIB0::24::INSTR')s

# Create a QCoDeS station and add the instruments
station = Station()
station.add_component(k6517a)
station.add_component(k2400)

# Create a sample object (assuming you have a Sample class defined)
sample = Sample(name="my_sample", file_path="/path/to/data/")

# Initialize the experiment
experiment = qc.new_experiment(name="my_experiment", sample_name=sample.name)

# Create a StaircaseSweep measurement for Keithley 6517A
sweep_6517a = StaircaseSweep(high_res=True, experiment=experiment, station=station, sample=sample)

# Configure and run the sweep for Keithley 6517A
sweep_6517a.set_parameters(start_v=-10, stop_v=10, step_v=0.1, npts_per_step=1, time_step=0.1, num_sweep=1)
sweep_6517a.configure_k6517a()
sweep_6517a.start_sweep()

# For Keithley 2400, we can use its built-in sweep functionality
k2400.configure_sweep_linear_staircase(
    start=-10,
    stop=10,
    step=0.1,
    mode='VOLT',
    compliance=1e-6,
    delay=0.1
)
k2400.run_sweep()

# To extend similar capabilities to Keithley 2400, we could create a new class:
class Keithley2400Sweep(StaircaseSweep):
    def __init__(self, experiment, station, sample, name=""):
        super().__init__(high_res=False, experiment=experiment, station=station, sample=sample, name=name)
        self.k2400 = station.k2400

    def configure_k2400(self):
        # Add configuration specific to Keithley 2400
        pass

    def start_sweep(self):
        self.k2400.configure_sweep_linear_staircase(
            start=self.sweep_arguments['start_v'],
            stop=self.sweep_arguments['stop_v'],
            step=self.sweep_arguments['step_v'],
            mode='VOLT',
            compliance=1e-6,
            delay=self.sweep_arguments['time_step']
        )
        self.k2400.run_sweep()
        # Add data acquisition and processing here

# Create and use the new Keithley2400Sweep
sweep_2400 = Keithley2400Sweep(experiment=experiment, station=station, sample=sample)
sweep_2400.set_parameters(start_v=-10, stop_v=10, step_v=0.1, npts_per_step=1, time_step=0.1, num_sweep=1)
sweep_2400.configure_k2400()
sweep_2400.start_sweep()
