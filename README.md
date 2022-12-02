# backup2022


`copyscanPZT-YZ`
- used for EIT spectroscopy
- scan the 970-ecdl via its piezo while recording wavemeter's reading
- software timed via `sleep()`. min ~ 10 ms according to rumors
- typically, when starting from scratch, `mean_voltage` in the main function is to be found manually
  
`logger_laserlock`
- used for characterizing the 405 lock
- log wavemeter reading in units of THz, sat ab voltage @ ai1, and digilock out @ port0/line7
- software timed via Qt.timeout~ 100 ms-1s per loop or data pt. slow, but the lock itself is fast

`logger_laserlockv2`
- used for locking the 970 laser to wavemeter via piezo control
- log wavemeter reading, error, servo Vout [ao1]
- controls ecdl;s piezo via Analog Remote Control (ARC) and Fine1. conversion factor =1 V/V. the ARC voltage is added to the scan offset 
- software timed~50 ms/loop. doing more things (e.g. read dac EIT ai) in each loop will slow this down 

`logger_laserlockv3`
- similar to v2 with reduced time lag at longer times 
