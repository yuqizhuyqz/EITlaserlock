from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QGridLayout, QLabel, \
    QVBoxLayout, QLineEdit, QCheckBox, QDoubleSpinBox, QMessageBox, QMainWindow
from PyQt5.QtCore import QTimer, QDateTime, Qt
import pyqtgraph as pg
import numpy as np
from os import path
import csv, sys, time
from datetime import datetime
from nidaqmx.task import Task, AcquisitionType   # for the DAQ
from nidaqmx.constants import TerminalConfiguration, LineGrouping, Edge
from ctypes import cdll, c_double, c_long  # for the wavemeter
from toptica.lasersdk.dlcpro.v2_0_3 import DLCpro, SerialConnection, DeviceNotFoundError, DecopError  # , UserLevel
from scipy import signal
from nidaqmx.stream_writers import AnalogSingleChannelWriter

# wavemeter lib
SYSTEM_FOLDERNAME = "C:\\Windows\\System32"
WLM_DATA_FILE = "wlmData.dll"
WLM_DATA_PATH = path.join(SYSTEM_FOLDERNAME, WLM_DATA_FILE)

# digital input
digilockTTL = "Dev1/port0/line7"  # di0 reading--405 digilock out
# analog input
EITlockin = "Dev1/ai0"  # ai0 reading EIT lockin output
satab = 'Dev1/ai4'
# digital trigger
trig = "Dev1/port2/line0" # also PFI0

#analog output
scanV = 'Dev1/ao1'
# config devices/inputs
comm_port = 'COM11'  # 978 nm DLC pro

# filenames for logs
filename2 = 'lock970wmonly13_50ms'
# save to a G-drive folder
path_name = r'G:\Shared drives\RAY\data\october2022'
filename2 = path_name + '\\' +filename2

samplingintervalmsec=50 # min=10 ms
savebool=False
freqsetpt = 308.32290 # freq setpt in THz

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
                task_ai.ai_channels.add_ai_voltage_chan(EITlockin, terminal_config=TerminalConfiguration.RSE)
                task_ai.ai_channels.add_ai_voltage_chan(satab, terminal_config=TerminalConfiguration.RSE)
                task_ao.ao_channels.add_ao_voltage_chan(scanV, min_val=-10, max_val=10)
                self.aichannels=task_ai.channel_names
                self.dichannels=task_di.channel_names
                self.aochannels=task_ao.channel_names
                # digital trigger for ao task
                # task_ao.triggers.start_trigger.cfg_dig_edge_start_trig(
                #     trigger_source='Dev1/port2/line0', trigger_edge=Edge.RISING)
                #
                # task_ai.triggers.start_trigger.cfg_dig_edge_start_trig(
                #     trigger_source='Dev1/port2/line0', trigger_edge=Edge.RISING)

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

    def setAO(self, channelname, samples):
        """
        :param channelname: name of physical channel, e.g. 'Dev1/ai0'
        :param samples: samples as an array
        :return:
        """

        with Task() as task:
            if channelname in self.aochannels:
                task.ao_channels.add_ao_voltage_chan(channelname)
                task.write(samples, auto_start=True)
                # digital trigger for ao task
                # task.triggers.start_trigger.cfg_dig_edge_start_trig(
                #     trigger_source='Dev1/port2/line0', trigger_edge=Edge.RISING)

class Window(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        self.setWindowTitle('pid controller for 970')
        layout = QHBoxLayout() # add sub-layouts horizontally; order: left -> right
        self.setLayout(layout)

        leftbox = QVBoxLayout()  # add sub-layouts vertically; first one added appears 1st
        layout.addLayout(leftbox)

        self.initSave(leftbox)
        self.initWS7(leftbox)

        rightbox = QVBoxLayout()
        layout.addLayout(rightbox)

        # self.initTimer(rightbox, samplingintervalmsec)
        # self.initdaqDI(rightbox, digilockTTL, 'digilock')
        # self.initdaqAI(rightbox, EITlockin, 'EIT lockin')

        self.initdaqAO(rightbox, scanV)

        self.initPID(rightbox)

    def initPID(self, layout):
        self.Kp=QDoubleSpinBox()
        self.Kp_label=QLabel('Kp')
        self.Ki_label=QLabel('Ki')
        self.Ki=QDoubleSpinBox()
        self.Kd_label=QLabel('Kd')
        self.Kd=QDoubleSpinBox()

        self.Kp.setValue(0.4)
        self.Ki.setValue(0.4)
        self.Kd.setValue(0.5)

        initrow = QHBoxLayout()
        layout.addLayout(initrow)
        initrow.addWidget(self.Kp_label)
        initrow.addWidget(self.Kp)
        initrow.addWidget(self.Ki_label)
        initrow.addWidget(self.Ki)
        initrow.addWidget(self.Kd_label)
        initrow.addWidget(self.Kd)

    def initWS7(self, layout):
        self.readWS7_label = QLabel('wavemeter:')
        self.readWS7 = QLineEdit()
        self.readWS7.setReadOnly(True)
        self.fset_label = QLabel('target:')

        self.freqsetpt = QLineEdit()
        self.freqsetpt.setText("{:.9f}".format(freqsetpt))
        self.freqsetpt.textChanged.connect(self.setsetpt)
        self.setsetpt()
        self.error_label = QLabel('Error (ref-read) in GHz')

        # add to init row=2nd row
        initrow = QHBoxLayout()
        # layout.addLayout(initrow, 2, 1)
        layout.addLayout(initrow)
        initrow.addWidget(self.readWS7_label)
        initrow.addWidget(self.readWS7)
        initrow.addWidget(self.fset_label)
        initrow.addWidget(self.freqsetpt)
        layout.addWidget(self.error_label)

        try:
            self.WSdev= WavemeterWS7()
            self.readWS7.setText("{:.9f}".format(self.WSdev.frequency) + " THz")

            # # INITIALIZE a dataset:  plot, list and curve
            self.WSdata =[self.WSdev.frequency]
            # error list in GHz
            self.errorarry = [(self.freqsetptval-self.WSdev.frequency)*1000]
            self.graphWidget0 = pg.PlotWidget(background='w')

            # Change pen color + thickness
            pen = pg.mkPen(color=(114, 166, 151), width=3)
            # This is the plotted data/"curve"
            # self.WScurve = self.graphWidget.getPlotItem().plot(pen=pen)
            self.errocurve = self.graphWidget0.getPlotItem().plot(pen=pen)

            layout.addWidget(self.graphWidget0)
        except:
            self.readWS7.setText("unable to connect")

    def setsetpt(self):
        try:
            self.freqsetptval = float(self.freqsetpt.text())
        except:
            self.freqsetptval = freqsetpt

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
            self.DAQAIcurve = self.graphWidget.getPlotItem().plot(pen=pen)

            layout.addWidget(self.graphWidget)
        except:
            self.daq_stat.setText("error")

    def initSave(self, layout):

        # self.log_file = filename2 + ".csv"
        # Display the log file
        self.save_txt = QLabel('Save to ')
        self.log_file = QLineEdit()
        self.log_file.textEdited.connect(self.checkpath)
        self.log_file.setText(filename2 + ".csv")
        self.checkpath()

        self.save_btn = QPushButton('save now')
        self.save_btn.clicked.connect(self.savedata)

        # Add the widgets to the layout
        initrow = QHBoxLayout()
        layout.addLayout(initrow)
        initrow.addWidget(self.save_txt)
        initrow.addWidget(self.log_file)
        initrow.addWidget(self.save_btn)

    def checkpath(self):
        if path.exists(self.log_file.text()):
            self.log_file.setStyleSheet("QLineEdit"
                                        "{"
                                        "color : gray;"
                                        "}")
            self.save_txt.setText('Save to (exists)')
        else:
            self.log_file.setStyleSheet("QLineEdit"
                                        "{"
                                        "color : blue;"
                                        "}")
            self.save_txt.setText('Save to ')

    def savedata(self):
        if path.exists(self.log_file.text()):
            # check if file exists, add new to file name
            type='a'
        else:
            type='w'

        with open(self.log_file.text(), type, newline='') as file:
            writer = csv.writer(file)
            # writer.writerow(['time', 'freqTHz', 'errorMHz', 'Vout'])
            # data = np.column_stack((self.times, self.WSdata, self.errorarry*1000, self.DAQdataAO))
            writer.writerow(['time', 'errorMHz', 'Vout'])
            data = np.column_stack((self.times, self.errorarry*1000, self.DAQdataAO))
            writer.writerows(data)

    def initTimer(self, layout, samplingintervalmsec):
        # Use a timer to update plot and log data
        self.time_label = QLabel()
        timeDisplay = QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss')
        self.time_label.setText(timeDisplay)

        # self.timer = QTimer()
        # self.t0=datetime.now()
        # self.t0 = time.perf_counter()
        # elapsedsec = (self.t0-self.t0).total_seconds()
        # self.times = [elapsedsec]
        # self.timer.start(int(samplingintervalmsec))
        # Pause logging button
        # self.pause_btn = QPushButton("Pause")
        # self.pause_btn.setCheckable(True)
        # self.pause_btn.setChecked(True)

        initrow = QHBoxLayout()
        layout.addLayout(initrow)
        initrow.addWidget(self.time_label)

    def initdaqAO(self, layout, channel):
        try:
            daq=USBdaq()
            self.daq_label2 = QLabel(channel)
            self.daq_aostart = QPushButton('servo')
            self.daq_aostart.setCheckable(True)
            # start servo
            self.daq_aostart.clicked.connect(self.initservo)

            self.Vout_label = QLineEdit('0')

            initrow = QHBoxLayout()
            layout.addLayout(initrow)
            initrow.addWidget(self.daq_label2)
            initrow.addWidget(self.daq_aostart)
            initrow.addWidget(self.Vout_label)

            # output 0 for a sec,
            Vout=0
            daq.setAO(channel, np.ones(1)*Vout)

            # INITIALIZE a dataset:  plot, list and curve
            self.DAQdataAO =[Vout]

            self.graphWidget2  = pg.PlotWidget(background='w')
            # # Change pen color + thickness
            pen = pg.mkPen(color=(114, 166, 151), width=3)
            # # This is the plotted data/"curve"
            self.DAQAOcurve = self.graphWidget2.getPlotItem().plot(pen=pen)

            layout.addWidget(self.graphWidget2)
        except:
            self.daq_stat.setText("error")

    def initservo(self):

        if self.daq_aostart.isChecked():
            # reset time and error
            self.timer = QTimer()
            self.timer.start(int(samplingintervalmsec))

            # reset time everytime it's checked
            self.t0=datetime.now()
            elapsedsec = (self.t0-self.t0).total_seconds()

            # times = [0]
            # errorarray=[self.errorarry[-1]]
            # DAQAOarray=[self.DAQdataAO[-1]]
            # data = dict(time=times, error=errorarray, ao=DAQAOarray)

            self.times = [elapsedsec]
            # reset data arrays
            self.errorarry =[self.errorarry[-1]]
            self.DAQdataAO =[self.DAQdataAO[-1]]
            self.WSdata =[self.WSdata[-1]]

            # disable unnecessary stuff to save loop time
            self.readWS7.setEnabled(False)
            self.Vout_label.setEnabled(False)

            self.timer.timeout.connect(self.servoupdate)

            # self.servoupdate(times, errorarray, DAQAOarray)
            # self.timer.timeout.connect(lambda: self.servoupdate(times, errorarray, DAQAOarray))

        else:
            # reenable the unnecessary stuff
            self.readWS7.setEnabled(True)
            self.readWS7.setText("{:.9f}".format(self.WSdev.frequency) + " THz")
            self.Vout_label.setEnabled(True)
            self.Vout_label.setText('{0:.4f}'.format(self.DAQdataAO[-1]))


    def servoupdate(self):

        if self.daq_aostart.isChecked():
            self.t1 = datetime.now()
            elapsedsec = (self.t1-self.t0).total_seconds()
            self.times.append(elapsedsec)
            # times=np.append(times, elapsedsec)
            # update wavemeter
            # value1 = self.WSdev.frequency
            # self.WSdata = np.append(self.WSdata, value1)
            # self.readWS7.setText("{:.9f}".format(self.WSdev.frequency) + " THz")

            # update digilock and ai read
            daq=USBdaq()

            # value2 = daq.read1ch(digilockTTL, 1)[0]
            # value3 = daq.read1ch(EITlockin, 1)[0]
            # self.di_stat.setChecked(value2)
            # self.DAQdataAI=np.append(self.DAQdataAI, value3)
            # self.DAQAIcurve.setData(self.times, self.DAQdataAI)
            # self.daq_stat.setText('{0:.4f}'.format(value3) )

            # error from this loop
            error = (self.freqsetptval-self.WSdev.frequency)*1000 # error in GHz
            # print('error {0:.4f}'.format(error))
            # error from the last loop
            lasterror = self.errorarry[-1]
            try:
                second2lasterror = self.errorarry[-2]
            except:
                second2lasterror = lasterror

            self.errorarry = np.append(self.errorarry, error)
            # errorarray = np.append(errorarray, error)
            # print('lasterror {0:.4f}'.format(sum(self.errorarry)))

            Vout= (self.Kp.value()*(error) + self.Ki.value()*(sum(self.errorarry))*samplingintervalmsec +
                   self.Kd.value()*(error-2*lasterror+second2lasterror)/samplingintervalmsec)*.1
            # print(Vout)
            # dac's output range
            Vout=  max(Vout, -10)
            Vout= min(Vout, 10)

            daq.setAO(scanV, Vout)

            self.DAQdataAO=np.append(self.DAQdataAO, Vout)
            # DAQAOarray = np.append(DAQAOarray, Vout)
            # self.Vout_label.setText('{0:.4f}'.format(Vout))
            # print(len(errorarray))

            # update plots
            # if round(elapsedsec) % 2 == 0:
            self.errocurve.setData(self.times, self.errorarry)
            self.DAQAOcurve.setData(self.times, self.DAQdataAO)
            # self.errocurve.setData(times, errorarray)
            # self.DAQAOcurve.setData(times, DAQAOarray)

        else:
            # clear graphs
            # self.graphWidget.removeItem(self.DAQAIcurve)
            self.graphWidget2.removeItem(self.DAQAOcurve)
            self.graphWidget0.removeItem(self.errocurve)

    def closeEvent(self, event):
        '''
        pop up a message box before closing
        :param event:
        :return:
        '''
        reply = QMessageBox.question(self, 'Window Close', 'Change Scan Offset on dlc?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.Yes:
            with DLCpro(SerialConnection(comm_port)) as dlc:
            # set PZT offset with new value closer to setpt
                vold = dlc.laser1.scan.offset.get()
                try:
                    vnew = vold + self.DAQdataAO[-1]

                except:
                    vnew = vold

                dlc.laser1.scan.offset.set(vnew)
                # wait for x s
                time.sleep(.005)

                daq=USBdaq()
                daq.setAO(scanV, 0)
                time.sleep(.005)

            event.accept()
            print('Scan offset = {0:0.2f} V -> {0:0.2f} V'.format(vold, vnew))
        else:
            event.accept()



app = QApplication(sys.argv)
screen = Window()
screen.show()
sys.exit(app.exec_())
# times = []
# errorarray=[]
# DAQAOarray=[]
# data = dict(time=times, error=errorarray, ao=DAQAOarray)
#
# data['time'] = np.append(data['time'], 1)
# print(data['time'])