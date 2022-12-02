# lock characterization and software servo

`logger_laserlock`
- used for characterizing the 405 lock
- running the code generates a GUI. Unpause to start logging.
- log wavemeter reading in units of THz, sat ab voltage @ ai1, and digilock out @ port0/line7 
- software timed via `Qttimer.timeout()`~ 100 ms-1s per loop or data pt. slow, but the lock itself is fast

`logger_laserlockv3`
- used for locking the 970 laser to wavemeter via piezo control
- running the code generates a GUI; pid starts automatically
- control ecdl's piezo via Analog Remote Control (ARC) and Fine1
  - conversion factor =1 V/V. the ARC voltage is added to the scan offset 
  - Vout from dac ao1
- log error (actual-setpoint) in GHz, and servo Vout in volts
- software timed~60 ms/loop
- (optional) update Scan offset on dlc before closing
- (optional) data can be saved after daq 
  - max log time ~ 3 hours to avoid 'time lags' (gaining loop times) at late times
