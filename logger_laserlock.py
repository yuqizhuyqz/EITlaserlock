from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QGridLayout, QLabel, \
     QVBoxLayout, QLineEdit, QCheckBox, QDoubleSpinBox
from PyQt5.QtCore import QTimer, QDateTime, Qt
import pyqtgraph as pg
import numpy as np
from os import path
import csv, sys, time
from datetime import datetime
from nidaqmx.task import Task  # for the DAQ
from nidaqmx.constants import TerminalConfiguration, LineGrouping
from ctypes import cdll, c_double, c_long  # for the wavemeter

# wavemeter lib
SYSTEM_FOLDERNAME = "C:\\Windows\\System32"
WLM_DATA_FILE = "wlmData.dll"
WLM_DATA_PATH = path.join(SYSTEM_FOLDERNAME, WLM_DATA_FILE)

# digital input
digilockTTL = "Dev1/port0/line7"  # di0 reading--405 digilock out
# analog input
satab = 'Dev1/ai4'


# filenames for logs
filename2 = 'lock767-1'
# save to a G-drive folder
path_name = r'G:\Shared drives\RAY\data\November2022'
filename2 = path_name + '\\' +filename2

samplingintervalmsec=1000
savebool=True


class WavemeterWS7():

    def __init__(self):
        if path.exists(WLM_DATA_PATH):
            self.lib = cdll.LoadLibrary(WLM_DATA_PATH)

        else:
            raise OSError("wlmData.dll not found in "+SYSTEM_FOLDERNAME)

    @property
    def active(self):
        """
        Is there an active measurement?
        :return: 0 if no measurement active, 1, if a measurement is active
        :rtype: int
        """
        getter = self.lib.GetOperationState
        getter.restype = c_long
        result = getter(0)
        return int(result)

    @active.setter
    def active(self, new_val):
        """
        Start or stop the active measurement
        :param new_val: the command to start or stop
        :type new_val: boolean or int
        """
        states = {0: 'StopAll', 1: 'StartMeasurement'}
        setter = self.lib.Operation
        setter.restype = c_long
        # response = setter(getattr(self, 'cCtrl'+states[new_val]))

    @property
    def frequency(self):
        """
        Query the frequency of the light with the largest amplitude after grating
        analysis.
        :return: frequency (THz)
        :rtype: float
        """
        if not self.active:
            self.active=True
        # sleep(0.5)
        get_frequency = self.lib.GetFrequency
        get_frequency.restype = c_double
        frequency = get_frequency(0)
        return float(frequency)

class USBdaq():
    def __init__(self):
        try:
            with Task() as task_di, Task() as task_ai, Task() as task_ao:
                # need different tasks for ai & di
                task_di.di_channels.add_di_chan(digilockTTL, line_grouping=LineGrouping.CHAN_PER_LINE)
                # task_ai.ai_channels.add_ai_voltage_chan(EITlockin, terminal_config=TerminalConfiguration.RSE)
                task_ai.ai_channels.add_ai_voltage_chan(satab, terminal_config=TerminalConfiguration.RSE)
                # task_ao.ao_channels.add_ao_voltage_chan(scanV) # USB6002 has no sampling clock, trig options for ao

                self.aichannels=task_ai.channel_names
                self.dichannels=task_di.channel_names
                self.aochannels=task_ao.channel_names
        except:
            raise OSError('failed to init usb daq')

    def read1ch(self, channelname, N):
        '''
        :param channelname:  name of physical channel, e.g. 'Dev1/ai0'
        :param N: number of samples to read
        :return: Nx1 array
        '''
        with Task() as task:
            if channelname in self.aichannels:
                task.ai_channels.add_ai_voltage_chan(channelname, terminal_config=TerminalConfiguration.RSE)
            elif channelname in self.dichannels:
                task.di_channels.add_di_chan(channelname, line_grouping=LineGrouping.CHAN_PER_LINE)
            return task.read(N)

class Window(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.setWindowTitle('405 Laser lock logger')
        layout = QHBoxLayout() # add sub-layouts horizontally; order: left -> right
        self.setLayout(layout)

        leftbox = QVBoxLayout()  # add sub-layouts vertically; first one added appears 1st
        layout.addLayout(leftbox)
        self.initSave(leftbox)
        self.initWS7(leftbox)

        rightbox = QVBoxLayout()
        layout.addLayout(rightbox)
        # # Default sampling rate in ms (min=1ms)
        self.initTimer(rightbox, samplingintervalmsec)

        self.initdaqDI(rightbox, digilockTTL, 'digilock')

        self.initdaqAI(rightbox, satab, 'sat ab')

        # Trigger update function on timeout

        self.timer.timeout.connect(self.update)

    def initWS7(self, layout):
        self.readWS7_label = QLabel('wavemeter:')
        self.readWS7 = QLineEdit()
        self.readWS7.setReadOnly(True)

        # add to init row=2nd row
        initrow = QHBoxLayout()
        # layout.addLayout(initrow, 2, 1)
        layout.addLayout(initrow)
        initrow.addWidget(self.readWS7_label)
        initrow.addWidget(self.readWS7)


        try:
            self.WSdev= WavemeterWS7()
            # self.WSdev.active(True)
            self.readWS7.setText("{:.9f}".format(self.WSdev.frequency) + " THz")

            # # INITIALIZE a dataset:  plot, list and curve
            self.WSdata =[self.WSdev.frequency]
            self.graphWidget = pg.PlotWidget(background='w')

            # Change pen color + thickness
            pen = pg.mkPen(color=(114, 166, 151), width=3)
            # This is the plotted data/"curve"
            self.WScurve = self.graphWidget.getPlotItem().plot(pen=pen)

            # row3 = QGridLayout()
            # layout.addLayout(row3, 3, 1)
            # row3.addWidget(self.graphWidget, 2, 2)
            layout.addWidget(self.graphWidget)
        except:
            self.readWS7.setText("unable to connect")

    def initdaqDI(self, layout, channel, name):
        self.di_stat = QCheckBox(name + '@')
        try:
            daq = USBdaq()
            # INITIALIZE a dataset: list
            self.DAQdataDI =daq.read1ch(channel,1)*1

            self.di_stat = QCheckBox(name+'@ '+ channel)
            # when it is pressed from unchecked state
            self.di_stat.setStyleSheet("QCheckBox::indicator::checked"
                                       "{"
                                       "background-color : green;"
                                       "}")

            self.di_stat.setChecked(daq.read1ch(channel,1)[0])
            # self.di_stat.setCheckable(False)
        except:
            self.di_stat.setEnabled(False)
            raise OSError('failed to init usb daq')

        # Add the widgets to the layout
        layout.addWidget(self.di_stat)

    def initdaqAI(self, layout, channel, name):
        self.daq_label = QLabel(name + '@ '+ channel)
        self.daq_stat = QLineEdit()
        self.daq_stat.setReadOnly(True)

        initrow = QHBoxLayout()
        layout.addLayout(initrow)
        initrow.addWidget(self.daq_label)
        initrow.addWidget(self.daq_stat)

        try:
            daq=USBdaq()
            self.daq_stat.setText('{0:.4f}'.format((daq.read1ch(channel, 1)[0])))

            # INITIALIZE a dataset:  plot, list and curve
            self.DAQdataAI =daq.read1ch(channel, 1)
            self.graphWidget = pg.PlotWidget(background='w')

            # # Change pen color + thickness
            pen = pg.mkPen(color=(114, 166, 151), width=3)
            # # This is the plotted data/"curve"
            self.DAQcurve = self.graphWidget.getPlotItem().plot(pen=pen)

            layout.addWidget(self.graphWidget)
        except:
            self.daq_stat.setText("error")

    def initSave(self, layout):
        self.log_file = filename2 + ".csv"
        # Display the log file
        self.save_txt = QLabel('Saving to ' + self.log_file)

        # Add the widgets to the layout
        layout.addWidget(self.save_txt)

        if savebool:
            if path.exists(self.log_file):
                # check if file exists, add new to file name
                type='a'
            else:
                type='w'

            with open(self.log_file, type, newline='') as file:
                writer = csv.writer(file)
                writer.writerow(['time','freq','digilock', 'sat ab'])
        else:
            self.save_txt.setEnabled(False)

        # Add the widgets to the layout
        # row1 = QHBoxLayout()
        # row1.addWidget(self.save_txt)
        # row1.addWidget(self.save_btn, 1, 2)
        # row1.addWidget(self.file_btn, 1, 2)

    def initTimer(self, layout, samplingintervalmsec):
        # Use a timer to update plot and log data
        self.time_label = QLabel()
        timeDisplay = QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
        self.time_label.setText(timeDisplay)

        self.timer = QTimer()
        self.t0=datetime.now()
        # self.t0 = time.perf_counter()
        elapsedsec = (self.t0-self.t0).total_seconds()

        self.times = [elapsedsec]
        self.timer.start(int(samplingintervalmsec))

        # Pause logging button
        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setCheckable(True)
        self.pause_btn.setChecked(True)

        initrow = QHBoxLayout()
        layout.addLayout(initrow)
        initrow.addWidget(self.time_label)
        initrow.addWidget(self.pause_btn)

    def update(self):
        """Updates the plot and logs new data."""
        if not self.pause_btn.isChecked():
            t1 = datetime.now()
            # t1=time.perf_counter()
            elapsedsec = (t1-self.t0).total_seconds()
            self.times.append(elapsedsec)
            timeDisplay = QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
            self.time_label.setText(timeDisplay)
            # Must convert the datetime object to timestamp format
            # time_axis = [i.timestamp() for i in self.times]

            # update wavemeter
            value1 = self.WSdev.frequency
            self.WSdata = np.append(self.WSdata, value1)
            self.WScurve.setData(self.times, self.WSdata)
            self.readWS7.setText("{:.9f}".format(self.WSdev.frequency) + " THz")

            daq = USBdaq()
            value2 = daq.read1ch(digilockTTL, 1)[0]
            value3 = daq.read1ch(satab, 1)[0]
            self.di_stat.setChecked(value2)

            self.DAQdataAI=np.append(self.DAQdataAI, value3)
            self.DAQcurve.setData(self.times, self.DAQdataAI)
            self.daq_stat.setText('{0:.4f}'.format(value3) )

            # Save to file. Append if exists, otherwise create.
            if savebool:
                with open(self.log_file, 'a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([elapsedsec, value1, value2*1, value3])


app = QApplication(sys.argv)
screen = Window()
screen.show()
sys.exit(app.exec_())
