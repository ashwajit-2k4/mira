------------------------------------------------------------------------
-- Author      : Suchet Gopal
-- Description : Master Scheuduler which coordinates the scheduling of 
--               all 16 I2C buses. Provided data output to the FIFO and 
--               takes input as commands from SPI or UART
------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use IEEE.MATH_REAL.ALL;

entity tmag_scheduling_core is 
    port (
        clk         : in  STD_LOGIC;
        reset       : in  STD_LOGIC;
        comm_in     : in  STD_LOGIC_VECTOR (7 downto 0);  -- Input Command from communication interface
        comm_in_v   : in  STD_LOGIC;                      -- Valid for above
        frame_out   : out STD_LOGIC_VECTOR (63 downto 0); -- Data Packet to FIFO 
        frame_out_v : out STD_LOGIC;                      -- Valid for above
        scl         : in  STD_LOGIC_VECTOR (15 downto 0); -- I2C Bus SCL inputs
        sda         : in  STD_LOGIC_VECTOR (15 downto 0); -- I2C Bus SDA inputs
        scl_en      : out STD_LOGIC_VECTOR (15 downto 0); -- Enable for SCL outputs
        sda_en_n    : out STD_LOGIC_VECTOR (15 downto 0)  -- Enable for SDA outputs

    );
end tmag_scheduling_core;

--Packet Format:
-- Header (1) = 0b1, Pix ID Upper (3), Timestamp (8), Z Data (16), Y Data [15:12] (4)
-- Parity (1)      , Pix ID Lower (3),                Y Data [11:0] (12), X Data (16)
-- Parity is such that every packet has an even number of 1s.

architecture Behavioral of tmag_scheduling_core is



  component data_merge is -- Handles merging of 16 to 1 streams. 
    port (
        clk          : in  std_logic;
        reset        : in  std_logic; 
		  data_in_v_comm : in std_logic;           -- Command ACK valid
        data_in_v_0  : in  std_logic;              -- Input valid signals for Bus 0 - 15
        data_in_v_1  : in  std_logic;
        data_in_v_2  : in  std_logic;
        data_in_v_3  : in  std_logic;
        data_in_v_4  : in  std_logic;
        data_in_v_5  : in  std_logic;
        data_in_v_6  : in  std_logic;
        data_in_v_7  : in  std_logic;
        data_in_v_8  : in  std_logic;
        data_in_v_9  : in  std_logic;
        data_in_v_10 : in  std_logic;
        data_in_v_11 : in  std_logic;
        data_in_v_12 : in  std_logic;
        data_in_v_13 : in  std_logic;
        data_in_v_14 : in  std_logic;
        data_in_v_15 : in  std_logic;
		  
		  data_in_comm : in  std_logic_vector(63 downto 0); -- Command ACK packet
        data_in_0    : in  std_logic_vector(63 downto 0); -- 64-bit input data
        data_in_1    : in  std_logic_vector(63 downto 0);
        data_in_2    : in  std_logic_vector(63 downto 0);
        data_in_3    : in  std_logic_vector(63 downto 0);
        data_in_4    : in  std_logic_vector(63 downto 0);
        data_in_5    : in  std_logic_vector(63 downto 0);
        data_in_6    : in  std_logic_vector(63 downto 0);
        data_in_7    : in  std_logic_vector(63 downto 0);
        data_in_8    : in  std_logic_vector(63 downto 0);
        data_in_9    : in  std_logic_vector(63 downto 0);
        data_in_10   : in  std_logic_vector(63 downto 0);
        data_in_11   : in  std_logic_vector(63 downto 0);
        data_in_12   : in  std_logic_vector(63 downto 0);
        data_in_13   : in  std_logic_vector(63 downto 0);
        data_in_14   : in  std_logic_vector(63 downto 0);
        data_in_15   : in  std_logic_vector(63 downto 0);

        data_out_v   : out std_logic;              -- Output valid signal
        data_out     : out std_logic_vector(63 downto 0) -- 32-bit output data
    );
end component;

component tmag_bus_scheduler is
    generic (
        pix1 : std_logic_vector(5 downto 0) := "000000";
        pix2 : std_logic_vector(5 downto 0) := "000001";
        pix3 : std_logic_vector(5 downto 0) := "000010";
        pix4 : std_logic_vector(5 downto 0) := "000011"
    );
    Port (
        clk              : in  std_logic;
        reset            : in  std_logic;
        bus_sch_v        : in  std_logic;
        bus_sch_command  : in  std_logic_vector(1 downto 0); -- "01" = boot, "10" = get_data
        timestamp_slv    : in  std_logic_vector(7 downto 0);
        cmd_done         : out std_logic;
        data_ack         : out std_logic;
        data             : out std_logic_vector(63 downto 0);
        scl              : in  std_logic;
        sda              : in  std_logic;
        scl_en           : out std_logic;
        sda_en_n         : out std_logic
    );
end component;




    type machine_state is (idle, wait_on_ack, scheduling); -- State of overall scheduler
    type slv64_array is array (15 downto 0) of std_logic_vector(63 downto 0);

    constant disabled : STD_LOGIC_VECTOR(15 downto 0) := x"FFFF"; -- In case of bad/noisy buses. disabled (i) = '0' => bus i is disabled
        
    signal sch_state : machine_state; 
    signal bus_sch_v : STD_LOGIC_VECTOR (15 downto 0) := (others => '0');
    signal bus_sch_ack : STD_LOGIC_VECTOR (15 downto 0) := (others => '0');
    signal cmd_done    : STD_LOGIC_VECTOR (15 downto 0) := (others => '0');



    signal bus_sch_busy : STD_LOGIC_VECTOR (15 downto 0) := (others => '0');
    signal bus_sch_command : STD_LOGIC_VECTOR (1 downto 0);

    signal data_ack : STD_LOGIC_VECTOR (15 downto 0) := (others => '0');
    signal data : slv64_array;

    signal interrupt : STD_LOGIC;
    signal ack_data : STD_LOGIC_VECTOR(63 downto 0);




    signal readout_en : STD_LOGIC;

    signal comm_ack : STD_LOGIC;

    signal counter : INTEGER;
    constant divider : INTEGER := 120_000_000/400; -- Divider controls sampling rate. This gives the peak value of 0.4 ksps.

    constant ones: STD_LOGIC_VECTOR (15 downto 0) := (others => '1');
    constant placeholder : STD_LOGIC_VECTOR (15 downto 0) := x"A0A0";
    
    

    signal timestamp_slv : STD_LOGIC_VECTOR (7 downto 0);
    signal timestamp : UNSIGNED (7 downto 0);
    
    constant boot_conf     : STD_LOGIC_VECTOR (7 downto 0) := "10100001"; -- Commands. Boot config   = A1
    constant start_readout : STD_LOGIC_VECTOR (7 downto 0) := "01010001"; --           Start Readout = 51
    constant stop_readout  : STD_LOGIC_VECTOR (7 downto 0) := "01010010"; --           Stop  Readout = 52

begin

    decoder_proc : process (clk, reset)
    begin
        if reset = '1' then 
            sch_state   <= idle;
            bus_sch_command <= "00";
            bus_sch_v <= (others => '0');
            comm_ack <= '0';
            bus_sch_ack <= (others => '0');

        elsif rising_edge(clk) then

            case sch_state is -- Overall Scheduler FSM
                when idle => 
                    comm_ack <= '0';
                    bus_sch_v <= (others => '0');
                    if comm_in_v = '1' then
                        if comm_in = boot_conf then
                            sch_state <= scheduling; -- Start config
                            bus_sch_command <= "01";
                            comm_ack <= '1';
                            ack_data <= x"ACCACCBEA1A1A1A1"; -- Send Command received ACK
                        elsif comm_in = start_readout then
                            sch_state <= scheduling; -- Start readout
                            bus_sch_command <= "10";
                            readout_en <= '1'; -- Update readout mode internal flag
                            comm_ack <= '1';
                            ack_data <= x"ACCACCBE51515151"; -- Send Command received ACK
                        end if;
                    else 
                        sch_state <= idle;
                        bus_sch_command <=  "00";
                    end if;
                when scheduling =>
                    comm_ack <= '0';
                    if comm_in_v = '1' and comm_in = stop_readout then
                        readout_en <= '0'; -- Disable readout gracefully (after the current frame ends)
                    end if;
                    if bus_sch_command = "01" then
                        bus_sch_v <= (others => '1');
                        sch_state <= wait_on_ack; -- Validate loaded command and wait for execution
                    else
                        if readout_en = '1' then -- Restart new frame
                            if interrupt = '1' then -- Clock trig at 0.4ksps
                                bus_sch_v <= (others => '1');
                                sch_state <= wait_on_ack; -- Restart acquisition
  
                            else 
                                bus_sch_v <= (others => '0');
                                sch_state <= scheduling;
                            end if;
                        else 
                            bus_sch_v <= (others => '0');
                            sch_state <= idle;
                        end if;
                    end if;

                when wait_on_ack => 

                    bus_sch_v <= (others => '0');
                    if comm_in_v = '1' and comm_in = stop_readout then
                        readout_en <= '0'; -- Gracefully stop as described above
                    end if;
                    if bus_sch_ack = (ones and disabled) then -- All enabled buses done 
                        bus_sch_ack <= (others => '0');
                        if bus_sch_command = "01" then
                            comm_ack <= '1';
                            ack_data <= x"ACCACCBE"  & (ones & ("00000000" & boot_conf)); -- Send boot complete ack
                            sch_state <= idle;
                        elsif bus_sch_command = "10" then
                       
                            if readout_en = '1' then
                                sch_state <= scheduling; -- Restart frame acquisition if in readout mode
                            else
                                sch_state <= idle;
                            end if;
                        end if;
                    else 
                        sch_state <= wait_on_ack;
                        bus_sch_ack <= bus_sch_ack or cmd_done; -- Keep checking status of bus schedulers
                    end if;
            end case;

        end if;
    end process;

    --frame_out_v <= comm_ack;
    --frame_out   <= ack_data;
    

    fifo_merge : data_merge 
    port map(
        clk => clk,
        reset => reset,
        data_in_v_comm => comm_ack,
        data_in_v_0 => data_ack(0),
        data_in_v_1 => data_ack(1),
        data_in_v_2 => data_ack(2),
        data_in_v_3 => data_ack(3),
        data_in_v_4 => data_ack(4),
        data_in_v_5 => data_ack(5),
        data_in_v_6 => data_ack(6),
        data_in_v_7 => data_ack(7),
        data_in_v_8 => data_ack(8),
        data_in_v_9 => data_ack(9),
        data_in_v_10 => data_ack(10),
        data_in_v_11 => data_ack(11),
        data_in_v_12 => data_ack(12),
        data_in_v_13 => data_ack(13),
        data_in_v_14 => data_ack(14),
        data_in_v_15 => data_ack(15),
        data_in_comm => ack_data,
        data_in_0 => data(0),
        data_in_1 => data(1),
        data_in_2 => data(2),
        data_in_3 => data(3),
        data_in_4 => data(4),
        data_in_5 => data(5),
        data_in_6 => data(6),
        data_in_7 => data(7),
        data_in_8 => data(8),
        data_in_9 => data(9),
        data_in_10 => data(10),
        data_in_11 => data(11),
        data_in_12 => data(12),
        data_in_13 => data(13),
        data_in_14 => data(14),
        data_in_15 => data(15),
        data_out_v => frame_out_v,
        data_out => frame_out
    );

    timer_proc : process (clk, reset) begin
        if reset = '1' then
            interrupt <= '1';
            counter <= 0;
            timestamp <= to_unsigned(0, 8);
        elsif rising_edge(clk) then
            if counter = divider then
                interrupt <= '1';
                counter   <= 0;
                timestamp <= timestamp + to_unsigned(1, 8);
            else
                counter <= counter + 1;
                interrupt <= '0';
            end if;
        end if;
    end process;

    timestamp_slv <= STD_LOGIC_VECTOR(timestamp);

    gen_schedulers : for i in 0 to 15 generate --Port map pixels with  unique pixel IDs and I2C lanes
        tmag_bus_scheduler_i : tmag_bus_scheduler
        generic map (
            pix1 => std_logic_vector(to_unsigned(i * 4, 6)),
            pix2 => std_logic_vector(to_unsigned(i * 4 + 1, 6)),
            pix3 => std_logic_vector(to_unsigned(i * 4 + 2, 6)),
            pix4 => std_logic_vector(to_unsigned(i * 4 + 3, 6))
        )
        port map (
            clk => clk,
            reset => reset,
            bus_sch_v => bus_sch_v(i) and disabled(i),
            bus_sch_command => bus_sch_command,
            timestamp_slv => timestamp_slv,
            cmd_done => cmd_done(i),
            data_ack => data_ack(i),
            data => data(i),
            scl => scl(i),
            sda => sda(i),
            scl_en => scl_en(i),
            sda_en_n => sda_en_n(i)
        );
    end generate;




end architecture;