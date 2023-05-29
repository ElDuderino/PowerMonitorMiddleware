# BESSMiddleware

The objective of this middleware will be to read critical parameters from a battery energy storage system and send the data to Aretas IoT cloud platform. 

The test system is a 2kW BESS with Daly BMS and Leaf cells in a 14S config. We refer to the 14S pack as HV Batt. So HV Batt Voltage and HV Batt Current measure
the whole system voltage and current ingress / egress. Measurement parameters include:

1. HV Batt Voltage
2. HV Batt Current (Charge / Discharge)
3. Temperatures (pack and environment)
4. Cell Voltages
5. State of charge
6. Statuses (charging, load, etc)
7. Capacity (Ah)
