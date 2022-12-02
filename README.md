# lock characterization and software servo

`logger_laserlock`
- used for characterizing the 405 lock
- running the code generates a two-panel GUI
- log wavemeter reading in units of THz, sat ab voltage @ ai1, and digilock out @ port0/line7
- software timed via Qt.timeout~ 100 ms-1s per loop or data pt. slow, but the lock itself is fast

`logger_laserlockv3`
- used for locking the 970 laser to wavemeter via piezo control
- running the code generates a GUI
- control ecdl's piezo via Analog Remote Control (ARC) and Fine1
  - conversion factor =1 V/V. the ARC voltage is added to the scan offset 
  - Vout from dac ao1
- log wavemeter reading in units of THz, error in THz, and servo Vout in volts
- software timed~60 ms/loop
