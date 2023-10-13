# PowerMonitorMiddleware

Since we can't fork our own repos, this is an import / copy of the BESSMiddleware (https://github.com/ElDuderino/BESSMiddleware) project that uses Daly BMS and optional dual XDM1041 meters for high precision current / voltage.

This version will ONLY read in the XDM1041 parameters and send them to the cloud. 

We'll output:
 * Current
 * Voltage
 * kWh
You could therefore use this package with the original BESSMiddleware (or any other middleware) but just disable the other middleware from outputting Current, Voltage and kWh

You must install the AretasPythonAPI from https://github.com/AretasSensorNetworks/AretasPythonAPI
You must also install the XDM1041 Driver from https://github.com/ElDuderino/XDM1041Python
