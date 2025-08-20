Containts all VHDL files necessary to generate the bistream for the CMOD A7.

To regenerate the bitstream, take the following steps:
1. Create a Vivado Project (tested on 2022.1) with the Board as CMOD A7 - 15T or CMOD A7 - 35T based on device type
2. Add all the VHDL files as design sources and the XDC file as a constraint.
3. Add a Clocking Wizard IP from the IP Catalog. Configure its input clock as 12 MHz and clk_out_1 as 120MHz.
4. Run Generate Bitstream.

### Overall working of the HDL:  
The Main readout hardware is interfaced with via SPI. In this way, commands are sent and data is received.
A Frame consists of 64 Packets, one from each pixel. We have 16 I2C Masters that are controlled by 16 Bus Schedulers. 
These Bus Schedulers are given commands by the Scheduling Core and return the output data and acknowledgements. 
The output data is stored in a 64 Packet deep FIFO for SPI readout.

### Boot-up sequence of the FPGA
On reset, the first command that should be sent is 'A1H'. This is the boot command and configures the sensors for readout. If new boot configurations are desired, the boot_wd part of the FSM logic in tmag_bus_scheduler can be updated. This will reflect for all sensors.  

After this, the command '51H' triggers the start of readout and will cause data packets to start accumulating in the FIFO. The Master device should be ready to read as soon as this command is sent to avoid data loss. An 8 bit timestamp can be used to track packet continuity or dropping. 

The 64 bit data is present in the following format: 

Header (1) = 0b1, Pix ID Upper (3), Timestamp (8), Z Data (16), Y Data [15:12] (4)
Parity (1)      , Pix ID Lower (3),                Y Data [11:0] (12), X Data (16)
Parity is such that every packet has an even number of '1's.

Once the readout is complete, send the command '52H'to stop readout. There may be some left-over data in the FIFO which should be emptied until '0x0' is receieved to setup the system properly for the next readout.
