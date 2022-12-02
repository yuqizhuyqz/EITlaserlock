import matplotlib.pyplot as plt
import numpy as np
from time import time, sleep
import os
import scipy.io as sio
from toptica.lasersdk.dlcpro.v2_0_3 import DLCpro, SerialConnection, DeviceNotFoundError, DecopError  # , UserLevel
from toptica.lasersdk.utils.dlcpro import extract_float_arrays
from nidaqmx.task import Task  # for the DAQ
from nidaqmx.constants import TerminalConfiguration
from ctypes import WinDLL, c_double, c_long  # for the wavemeter
from get_data_from_DLCPro.read_EIT import locate_voltage

# config devices/inputs
comm_port = 'COM11'  # 978 nm DLC pro

# locksatab = "Dev1/ai3"  # ai3 reading 405 sat ab PDA
EITlockin = "Dev1/ai0"  # ai0 reading EIT lockin output

# This is the wavemeter - make sure GUI is open, and it's reading the IR wavelength
dll = WinDLL(r"C:\Windows\System32\wlmData.dll")
dll.GetFrequencyNum.restype = c_double


# in case data is to be saved
saveBool = False
filename = 'scan0'

path_name = r'G:\Shared drives\RAY\data\September2022'
filename = path_name + '\\' +filename
memo = 'data: w.m. reading [THz], lockin-avg [V], -error [V], -waveform, pzt reading [V], (relative) time stamp'

def scan_and_recordv2(file_name, readme, scanoffset, scanamp, step_size, samplesperstep, save=False, plot=False):
    """
    Scans and records data from the DLC Pro, the wavemeter, and the DAQ
    :param file_name:
    :param scanoffset: PZT voltage offset [V] as on DLC pro
    :param scanamp: amplitude/range [V] of the scan
    :param step_size: PZT step size [V] in this scan
    :param samplesperstep: number of samples per channel to collect from DAQ for the lockin output
    :param save: boolean to save the npz file
    :param plot: boolean to plot the data taken
    :return: nothing
    """

    try:
        with DLCpro(SerialConnection(comm_port)) as dlc, Task() as task:
            try:
                # print(' \n DLC Time :', dlc.time.get())
                print("DLC scanning from {:.3f} V to  {:.3f} V in {} steps of "
                      "{:.3f} V/step \n".format(scanoffset - scanamp/2,
                        scanoffset + scanamp/2, np.ceil(scanamp/step_size),
                        step_size))

                # read 405 lock sat ab level
                # task.ai_channels.add_ai_voltadaqwaveforge_chan(locksatab, terminal_config=TerminalConfiguration.RSE)

                # read EIT lock in output via daq
                task.ai_channels.add_ai_voltage_chan(EITlockin, terminal_config=TerminalConfiguration.RSE)

                print("DAQ reading EIT lock in output via", EITlockin, " \n")
                # print(' DLC Time :', dlc.time.get())

                # in each step, save 1 PZT reading
                piezo_voltage_read = []
                # save 1 wavemeter reading
                wavemeter_read = []
                # save 1 lockin average
                lockin_avg = []
                # save 1 lockin error
                lockin_error = []
                # save 1 timestamp
                time_stamp = []
                # save a lockin waveform with samplersperstep points for each step
                lockin_signal = []

                # record the initial PZT scan settings in DLC pro   (to restore later)
                start_values = (dlc.laser1.scan.amplitude.get(), dlc.laser1.scan.frequency.get())

                # starting time for time_stamp
                start_time = time()
                # PZT scan starts @
                current_voltage = scanoffset-scanamp/2

                while current_voltage <= (scanoffset + scanamp/2):
                    i = 0
                    # set PZT offset
                    dlc.laser1.scan.offset.set(current_voltage)
                    # wait for x s
                    sleep(.005)

                    #  get a PZT volt. reading from dlc pro-- save to array
                    piezo_voltage_read.append(dlc.laser1.scan.offset.get())
                    print('PZT set to {:.3f} V \n'.format(dlc.laser1.scan.offset.get()))

                    #  get a wavemeter reading--print and save to array
                    frequency = dll.GetFrequencyNum(c_long(1), c_double(0))
                    wavemeter_read.append(frequency)
                    print('wavemeter reading {:.7f} THz \n'.format(frequency))

                    #  get lockin waveform --print and save to array
                    lockinwaveform = task.read(samplesperstep)
                    lockin_signal.append(lockinwaveform)

                    # calculate mean/error from lockin waveform--print and save to array
                    lockin_avg.append(np.average(lockinwaveform))
                    lockin_error.append(np.std(lockinwaveform)/np.sqrt(np.size(lockinwaveform)))
                    print('lock in mean={:.3f} V error={:.6f} V'.format(np.average(lockinwaveform),
                                            np.std(lockinwaveform)/np.sqrt(np.size(lockinwaveform))))
                    # np.size(lockinwaveform)== samplesperstep

                    #  get lockin waveform --print and save to array  np.size(lockinwaveform)
                    time_stamp.append(time()-start_time)

                    # increase the PZT voltage by step_size
                    current_voltage += step_size

                # after the while loop,  set pzt scan settings to initial
                dlc.laser1.scan.amplitude.set(start_values[0])
                dlc.laser1.scan.frequency.set(start_values[1])

                if save:
                    # save data to a npz

                    np.savez(file_name, readme=readme, piezo=piezo_voltage_read,
                             lockinavg=lockin_avg, lockinerror=lockin_error, lockingwvfm=lockinwaveform,
                             wavemeter=wavemeter_read, time_stamp=time_stamp)

                if plot:
                    plt.figure()
                    x = np.array(wavemeter_read)*1e3
                    plt.errorbar(x, lockin_avg, yerr=lockin_error,  marker='s')
                    plt.xlabel('wavemeter reading [GHz]')
                    plt.ylabel('Averaged lock-in output [arb. unit]')
                    plt.title(dlc.time.get())
                    plt.show()

            except DecopError as error:
                print(error)

    except DeviceNotFoundError:
        print('Device not found')

def npz2mat(file_name):
    """
    convert npz to mat with identical filename, save under the same dir
    :param file_name:
    :return: nothing
    """
    data = np.load(file_name+'.'+'npz')

    sio.savemat(file_name+'.'+'mat', mdict={key: data[key] for key in data.keys()})

def main():
    # find scan voltage from freq.
    # start_voltage = locate_voltage(308.58989+ 720e-6)

# both peaks
    mean_voltage =36.4 # center of the scan
    scanamp=.1 #  scan amplitude, range=2*amp, both peaks
# v=0 peak
#     mean_voltage =36.7 # center of the scan
#     scanamp=.3 #  scan amplitude, range=2*amp
    res=0.007 #0.007

    # scan PZT save in a npz
    scan_and_recordv2(filename, memo, mean_voltage, scanamp, res, 10, save=saveBool, plot=True)

    if saveBool:
        # convert npz to mat
        npz2mat(filename)
        # delete the npz file
        os.remove(filename+'.'+'npz')

if __name__ == "__main__":
    main()