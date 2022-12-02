from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QHBoxLayout, QGridLayout, QLabel, \
    QVBoxLayout, QLineEdit, QCheckBox, QDoubleSpinBox, QMessageBox, QMainWindow
from PyQt5.QtCore import QTimer, QDateTime, Qt, QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
import pyqtgraph as pg
import numpy as np
from os import path
import csv, sys, time, traceback
from datetime import datetime
from nidaqmx.task import Task, AcquisitionType   # for the DAQ
from nidaqmx.constants import TerminalConfiguration, LineGrouping, Edge
from ctypes import cdll, c_double, c_long  # for the wavemeter
from toptica.lasersdk.dlcpro.v2_0_3 import DLCpro, SerialConnection, DeviceNotFoundError, DecopError  # , UserLevel

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
filename2 = 'lock970wmonly18_60ms'
# save to a G-drive folder
path_name = r'G:\Shared drives\RAY\data\october2022'
filename2 = path_name + '\\' + filename2

samplingintervalmsec=60 # min=10 ms
savebool=False
freqsetpt = 308.32290 # freq setpt in THz

class WavemeterWS7(QWidget):

    # wavemeter lib
    SYSTEM_FOLDERNAME = "C:\\Windows\\System32"
    WLM_DATA_FILE = "wlmData.dll"
    WLM_DATA_PATH = path.join(SYSTEM_FOLDERNAME, WLM_DATA_FILE)

    def __init__(self, layout, *args, **kwargs):
        self.args =args
        self.kwargs =kwargs
        QWidget.__init__(self)

        if path.exists(self.WLM_DATA_PATH):
            self.lib = cdll.LoadLibrary(self.WLM_DATA_PATH)
        else:
            raise OSError("wlmData.dll not found in "+self.SYSTEM_FOLDERNAME)

        # def initWS7(self, layout):
        self.readWS7_label = QLabel('wavemeter:')
        self.readWS7 = QLineEdit()
        self.readWS7.setReadOnly(True)
        self.fset_label = QLabel('ref freq:')

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
            self.readWS7.setText("{:.9f}".format(self.frequency) + " THz")
            self.graphWidget0 = pg.PlotWidget(background='w')

            # Change pen color + thickness
            pen = pg.mkPen(color=(114, 166, 151), width=3)
            # This is the plotted data/"curve"

            # # # INITIALIZE a dataset:  plot, list and curve
            # self.data =np.append(self.data, self.frequency)
            # # error list in GHz
            # self.errorarry = [(self.freqsetptval-self.frequency)*1000]
            self.curve = self.graphWidget0.getPlotItem().plot(pen=pen)

            layout.addWidget(self.graphWidget0)
        except:
            self.readWS7.setText("unable to connect")

    def setsetpt(self):
        try:
            self.freqsetptval = float(self.freqsetpt.text())
        except:
            self.freqsetptval = freqsetpt

    @property
    def frequency(self):
        """
        Query the frequency of the light with the largest amplitude after grating
        analysis.
        :return: frequency (THz)
        :rtype: float
        """
        # if not self.active:
        #     self.active=True
        # # sleep(0.5)
        get_frequency = self.lib.GetFrequency
        get_frequency.restype = c_double
        frequency = get_frequency(0)
        return float(frequency)

class USBdaq(QWidget):
    channel =scanV
    def __init__(self, layout, *args, **kwargs):

        # allows for adding data collecting arrays, etc
        self.args =args
        self.kwargs =kwargs

        QWidget.__init__(self)
        try:
            with Task() as task_di, Task() as task_ai, Task() as task_ao:
                # need different tasks for ai & di
                task_di.di_channels.add_di_chan(digilockTTL, line_grouping=LineGrouping.CHAN_PER_LINE)
                task_ai.ai_channels.add_ai_voltage_chan(EITlockin, terminal_config=TerminalConfiguration.RSE)
                task_ao.ao_channels.add_ao_voltage_chan(scanV, min_val=-10, max_val=10)

                self.aichannels=task_ai.channel_names
                self.dichannels=task_di.channel_names
                self.aochannels=task_ao.channel_names

        except:
            raise OSError('failed to init usb daq')

        self.daq_label2 = QLabel(self.channel)
        # self.daq_aostart = QPushButton('servo')
        # self.daq_aostart.setCheckable(True)

        # start servo
        # self.daq_aostart.clicked.connect(self.initservo)

        self.Vout_label = QLineEdit('0')

        initrow = QHBoxLayout()
        layout.addLayout(initrow)
        initrow.addWidget(self.daq_label2)
        # initrow.addWidget(self.daq_aostart)
        initrow.addWidget(self.Vout_label)
        try:
            Vout=0
            self.setAO(self.channel, np.ones(1)*Vout)

            # # INITIALIZE a dataset:  plot, list and curve
            # self.DAQdataAO =[Vout]

            # self.graphWidget2  = pg.PlotWidget(background='w')
            # # # Change pen color + thickness
            # pen = pg.mkPen(color=(114, 166, 151), width=3)
            # # # This is the plotted data/"curve"
            # self.AOcurve = self.graphWidget2.getPlotItem().plot(pen=pen)
            #
            # layout.addWidget(self.graphWidget2)
        except:
            self.daq_stat.setText("error")

        # pid boxes and labels
        self.Kp=QDoubleSpinBox()
        self.Kp_label=QLabel('Kp')
        self.Ki_label=QLabel('Ki')
        self.Ki=QDoubleSpinBox()
        self.Kd_label=QLabel('Kd')
        self.Kd=QDoubleSpinBox()

        self.Kp.setValue(0.4)
        self.Ki.setValue(0.4)
        self.Kd.setValue(0.5)

        initrow2 = QHBoxLayout()
        layout.addLayout(initrow2)
        initrow2.addWidget(self.Kp_label)
        initrow2.addWidget(self.Kp)
        initrow2.addWidget(self.Ki_label)
        initrow2.addWidget(self.Ki)
        initrow2.addWidget(self.Kd_label)
        initrow2.addWidget(self.Kd)

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

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)

class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

class SaveStuff(QWidget):

    def __init__(self, layout, *args, **kwargs):
        QWidget.__init__(self)
        self.args = args
        self.kwargs = kwargs

        # Display the log file
        self.save_txt = QLabel('Save to ')
        self.log_file = QLineEdit()
        self.log_file.textEdited.connect(self.checkpath)
        self.log_file.setText(filename2 + ".csv")
        self.checkpath()
        self.save_btn = QPushButton('save now')
        # self.save_btn.clicked.connect(lambda: self.savedata(data))

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

class MainWindow(QMainWindow):
    ''' adapted from this example:
    https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/
    '''

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        layout = QHBoxLayout()
        leftbox = QVBoxLayout()  # add sub-layouts vertically; first one added appears 1st
        layout.addLayout(leftbox)
        save = SaveStuff(leftbox)

        wavemeter = WavemeterWS7(leftbox, errorarray=[], data=[])
        daq = USBdaq(leftbox, aoarray=[])

        self.setWindowTitle('pid controller for 970')
        self.setCentralWidget(daq)
        daq.setLayout(layout)

        # self.timer2.timeout.connect(lambda: self.initservo(wavemeter, daq))
        self.timer = QTimer()
        self.timer.start(int(samplingintervalmsec))
        # reset time everytime it's checked
        self.t0=datetime.now()
        elapsedsec = (self.t0-self.t0).total_seconds()
        self.times = [elapsedsec]
        # # reset data arrays

        # init error list in GHz
        wavemeter.errorarray = np.append([], (wavemeter.freqsetptval-wavemeter.frequency)*1000)
        daq.aoarray=np.append([], 0)

        # disable unnecessary stuff to save loop time
        wavemeter.readWS7.setEnabled(False)
        self.timer.timeout.connect(lambda: self.servoupdate(wavemeter, daq))

        self.threadpool = QThreadPool()
        save.save_btn.pressed.connect(lambda: self.savenow(save, wavemeter, daq))

        # re-init arrays every waittime in ms
        self.timer2 = QTimer()
        # waittime = 1000*3
        waittime = 1000*3600*3 %
        self.timer2.start(waittime)
        self.timer2.timeout.connect(lambda: self.timeout2(wavemeter, daq, save))

    def servoupdate(self, wavemeter, daq):

        self.t1 = datetime.now()
        elapsedsec = (self.t1-self.t0).total_seconds()
        self.times.append(elapsedsec)

        # error from this loop
        error = (wavemeter.freqsetptval-wavemeter.frequency)*1000 # error in GHz
        # error from the last loop
        lasterror = wavemeter.errorarray[-1]
        try:
            second2lasterror = wavemeter.errorarray[-2]
        except:
            second2lasterror = lasterror

        wavemeter.errorarray = np.append(wavemeter.errorarray, error)
        # DeltaV= (daq.Kp.value()*(error) + daq.Ki.value()*(error)*(elapsedsec-self.times[-2])*1000 +
        #        daq.Kd.value()*(error-2*lasterror+second2lasterror)/(elapsedsec-self.times[-2])/1000)*.1
        DeltaV= (daq.Kp.value()*(error) + daq.Ki.value()*(error)*(samplingintervalmsec) +
                 daq.Kd.value()*(error-2*lasterror+second2lasterror)/samplingintervalmsec)*.1
        # Vout= (daq.Kp.value()*(error) + daq.Ki.value()*(sum(wavemeter.errorarray))*samplingintervalmsec +
        #        daq.Kd.value()*(error-2*lasterror+second2lasterror)/samplingintervalmsec)*.1
        Vout= DeltaV + daq.aoarray[-1]
        # print(Vout)
        # dac's output range
        Vout=  max(Vout, -10)
        Vout= min(Vout, 10)

        daq.setAO(scanV, Vout)

        daq.Vout_label.setText('{0:.4f}'.format(Vout))
        daq.aoarray =np.append(daq.aoarray, Vout)

    # update plots
        n=100 # plot last 100 pt ~ 6 s
        wavemeter.curve.setData(self.times[-n:], wavemeter.errorarray[-n:])

    def updateplots(self, wavemeter, daq, progress_callback):
        n=100 # plot last n
        wavemeter.curve.setData(self.times[-n:], wavemeter.errorarray[-n:])
        daq.AOcurve.setData(self.times[-n:], daq.aoarray[-n:])

    def savedata(self, save, data, progress_callback):
        if path.exists(save.log_file.text()):
            # check if file exists, add new to file name
            type='a'
        else:
            type='w'

        with open(save.log_file.text(), type, newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['time', 'errorMHz', 'Vout'])
            # data = np.column_stack((self.times))
            # data = np.column_stack((self.times, self.errorarry*1000, self.DAQdataAO))
            writer.writerows(data)

    def savenow(self, save, wavemeter, daq):
        # Pass the function to execute
        data = np.column_stack((self.times, wavemeter.errorarray*1000, daq.aoarray))
        worker = Worker(self.savedata, save, data)
        # Execute
        self.threadpool.start(worker)

    def timeout2(self, wavemeter, daq, save):

        print('reinit. arrays on', QDateTime.currentDateTime().toString('yyyy-MM-dd hh:mm:ss'))
        save.log_file.setText(path_name + '\\' +'lock970autosave' +
                              QDateTime.currentDateTime().toString('yyyy_MM_dd_hh_mm')+'.csv')
        save.checkpath()
        self.savenow(save, wavemeter, daq)
        #
        self.initservo(wavemeter, daq, save, 0)

        # worker2 = Worker(self.initservo, wavemeter, daq, save)
        # self.threadpool.start(worker2)


    def initservo(self, wavemeter, daq, save, progress_callback):
        '''reinit servo--reinit arrays'''

        self.t0 = datetime.now()
        lastn =1
        self.times = [0]#self.times[-lastn:]
        # # reset data arrays
        # init error list in GHz
        wavemeter.errorarray = wavemeter.errorarray[-lastn:]
        daq.aoarray=daq.aoarray[-lastn:]

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

                daq = USBdaq(QHBoxLayout())
                daq.setAO(scanV, 0)
                time.sleep(.005)

            event.accept()
            print('Scan offset = {0:0.2f} V -> {0:0.2f} V'.format(vold, vnew))
        else:
            event.accept()


app = QApplication(sys.argv)
screen = MainWindow()
screen.show()
sys.exit(app.exec_())
