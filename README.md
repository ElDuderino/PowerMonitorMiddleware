# PowerMonitorMiddleware

This middleware allows you to read real-time voltage, current and power from a pair of OWON XDM1041 multimeters. One would use this 
to gain visibility into a BESS or remote battery system. The main benefits of using the OWON meters are a high grade of accuracy compared to  typical BMS resolution. 

The software will attempt to auto configure the meters. However, be aware that one meter should be measuring system voltage
(usually a high voltage) and the second meter is ALSO measuring voltage, but across a calibrated shunt.

The data is sent to the Aretas Cloud Platform as well as (optionally) a local Redis instance. The Redis instance only stores the 
latest readings, not the time series data. 

We'll output:
 * Current (A)
 * Voltage (V)
 * Power (kWh)

You must install the AretasPythonAPI from https://github.com/AretasSensorNetworks/AretasPythonAPI
You must also install the XDM1041 Driver from https://github.com/ElDuderino/XDM1041Python

## Config

Install the requirements found in requirements.txt

Copy config.cfg.example to a new file called config.cfg

**self_mac** = The MAC address of the device in the Aretas system

**API_URL** = Do not change this

**API_USERNAME** = Your username for the Aretas Cloud Platform
**API_PASSWORD** = Your password for the Aretas Cloud Platform

**report_interval** = How many milliseconds between sending packets to the Cloud API (should be something like 30000 for 30 seconds)

**sample_interval** = How many milliseconds between serial port reads. Should be shorter than the report_interval value... 5000 (5 seconds) is a good rule of thumb.

**xdm_current_enable** = Whether to measure current (or not)

**xdm_current_port** = The serial port for the current meter (operating in voltage mode, measuring shunt voltage e.g. COM1 or /tty/USB1 etc.)

**xdm_shunt_resistance** = The shunt resistance in Ohms, typically a very small value such as 0.0006667

**xdm_current_reverse_polarity** = The current "direction" is a function of how one connects the +/- leads 
of the voltmeter to the shunt terminals. One can "reverse" the reported current direction if desired.

**xdm_voltage_enable** = Whether to enable voltage measurements (or not)

**xdm_voltage_port** = The serial port for the voltage meter (operating in voltage mode)

## Running

The simplest way to run the middleware is to cd into the installation folder and run:

``python3 backend_daemon.py``

To view the output from the logs, check PowerMonitorMiddlware.log in the same folder. ```tail -f  PowerMonitorMiddleware.log```

For permanent installation and automatic startup, install the systemd service file:

## Installing the systemd service

Copy the systemd file found in systemd/powermonitormiddleware.service in this GitHub repo to ``/etc/systemd/system``

Open it with a text editor (e.g., ``sudo vim /etc/systemd/system/powermonitormiddleware.service``).

Change the relevant directories in ``ExecStart=`` and ``WorkingDirectory=`` to the full path where the middleware is installed.
Also edit the ``User=`` variable to change the user the service executes as.

Enable and Start the Service:

Reload the systemd manager configuration: ``sudo systemctl daemon-reload``.

Enable the service to start on boot: ``sudo systemctl enable powermonitormiddleware.service``.

Start the service: sudo systemctl start ``powermonitormiddleware.service``.

## Customizing ##

It's possible to support other configurations, where you are measuring current directly with the XDM1041, but you must determine the startup configuration for the meters, then edit:

```serial_port_read_writer.py```

Specifically in the ``__init__`` function, inspect the lines where the meter configuration happens (e.g. for current): ``self._xdm_current_device = XDM1041(XDM1041Mode.MODE_VOLTAGE_DC, 1, xdm_serial_port)``

Also look in ``do_fetch_params`` in ``serial_port_read_writer.py`` to override the computation logic for the current etc. 