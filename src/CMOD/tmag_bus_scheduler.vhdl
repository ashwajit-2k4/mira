------------------------------------------------------------------------
-- Author      : Suchet Gopal
-- Description : Handles I2C transactions for a single bus of 4 sensors
--               when given boot config or readout commands
------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity tmag_bus_scheduler is
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
        cmd_done         : out std_logic;                    -- '1' => Bus scheduling done
        data_ack         : out std_logic;                    -- '1' => Data valid to FIFO
        data             : out std_logic_vector(63 downto 0); -- Readout data
        scl              : in  std_logic;                     -- I2C clock input path
        sda              : in  std_logic;                     -- I2C data  input path
        scl_en           : out std_logic;
        sda_en_n         : out std_logic
    );
end tmag_bus_scheduler;

architecture Behavioral of tmag_bus_scheduler is

    COMPONENT i2c_master_ctrl IS
    PORT(
      clk       : IN     STD_LOGIC;                    --system clock
      reset     : IN     STD_LOGIC;                    --active low reset
      scl       : IN     STD_LOGIC;
      sda       : IN     STD_LOGIC;
      ena       : IN     STD_LOGIC;                    --latch in command
      addr      : IN     STD_LOGIC_VECTOR(6 DOWNTO 0); --address of target slave
      rw        : IN     STD_LOGIC;                    --'0' is write, '1' is read
      conv_trig : IN     STD_LOGIC;
      addr_ptr  : IN     STD_LOGIC_VECTOR(6 downto 0); --target register address within slave
      data_wr   : IN     STD_LOGIC_VECTOR(7 DOWNTO 0); --data to write to slave
      busy      : OUT    STD_LOGIC;                    --indicates transaction in progress
      data_rd   : OUT    STD_LOGIC_VECTOR(7 DOWNTO 0); --data read from slave
      data_rd_v : OUT    STD_LOGIC;
      i2c_error : OUT    STD_LOGIC;                    --flag if improper acknowledge from slave                  
      sda_en_n  : OUT    STD_LOGIC;                    --for serial data output of i2c bus
      scl_en    : OUT    STD_LOGIC                     --for serial clock output of i2c bus
  
      );                   
  END component;

    type scheduler_state is (idle, busop, ack);
    type substate_type is ( -- types of bytes to write/read from the TMAG3001
        boot_wd1, boot_wd2, boot_wd3, boot_wd4,
        getx_msb, getx_lsb,
        gety_msb, gety_lsb,
        getz_msb, getz_lsb
    );

    signal bus_sch_st    : scheduler_state := idle;
    signal bus_sch_ss    : substate_type := boot_wd1;
    signal load          : std_logic := '0';
    signal bus_sch_adr   : std_logic_vector(1 downto 0) := "00"; -- encoded address (ADDR Pin of TMAG3001 connectivity)
    signal i2c_en        : std_logic;
    signal i2c_rw        : std_logic;
    signal i2c_addr      : std_logic_vector(6 downto 0);
    signal i2c_addr_ptr  : std_logic_vector(6 downto 0);
    signal i2c_data_wr   : std_logic_vector(7 downto 0);
    signal i2c_data_rd   : std_logic_vector(7 downto 0);
    signal i2c_busy      : std_logic;
    signal i2c_busy_prev : std_logic;
    signal i2c_data_v    : std_logic;

    function get_adr(addr : std_logic_vector(1 downto 0)) return std_logic_vector is
    begin
        case addr is
            when "00" => return "0110101"; -- adr_vcc
            when "01" => return "0110100"; -- adr_gnd
            when "10" => return "0110110"; -- adr_sda
            when others => return "0110111"; -- adr_scl
        end case;
    end function;

begin

    process (clk, reset)
    begin
        if reset = '1' then -- Disable all I2C I/Os in case of reset, data invalid
            cmd_done <= '0';
            data_ack <= '0';
            data <= (others => '0');
            bus_sch_st <= idle;
            bus_sch_adr <= "00";
            load <= '0';
            i2c_en <= '0';
            i2c_addr <= "0110101"; -- Reset to 35H, first sensor in bus
            i2c_addr_ptr <= (others => '0');
            i2c_data_wr  <= (others => '0');
            i2c_rw       <= '0';
            
        elsif rising_edge(clk) then
            case bus_sch_st is
                when idle => -- Keep polling for boot or readout commands.
                    cmd_done <= '0';
                    data_ack <= '0';
                    if bus_sch_v = '1' then
                        bus_sch_st <= busop;
                        load <= '0';
                        bus_sch_adr <= "00";
                        if bus_sch_command = "01" then
                            bus_sch_ss <= boot_wd1;
                        elsif bus_sch_command = "10" then
                            bus_sch_ss <= getx_msb;
                        end if;
                    end if;

                when busop => -- Sequentially write/read bytes
                    data_ack <= '0';
                    case bus_sch_ss is
                        when boot_wd1 =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '0';
                                i2c_addr_ptr <= "0000000"; -- Config Reg @ 0H
                                i2c_data_wr <= "00010100"; -- CONV_AVG = 5H (32x averagign)
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1'; -- Wait for I2C to start
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= boot_wd2; -- Reload I2C master
                                end if;
                            end if;

                        when boot_wd2 =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '0';
                                i2c_addr_ptr <= "0000001"; -- Config Reg @ 1H
                                i2c_data_wr <= "00010010"; -- LP_LN = 1 (Low Noise mode), Operating Mode = 2H (continuous mode)
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= boot_wd3;
                                end if;
                            end if;

                        when boot_wd3 =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '0';
                                i2c_addr_ptr <= "0000011"; -- Config Reg @ 3H
                                i2c_data_wr <= "00000011"; -- Set max range (240 mT)
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= boot_wd4;
                                end if;
                            end if;

                        when boot_wd4 =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '0';
                                i2c_addr_ptr <= "0000010"; -- Config final reg @ 2H
                                i2c_data_wr <= "01110000"; -- Enable XYZ channels for readout
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    if bus_sch_adr = "00" then -- Move to next device on bus or send ack to scheduling core if done
                                        bus_sch_adr <= "01";
                                        bus_sch_ss  <= boot_wd1;
                                    elsif bus_sch_adr = "01" then
                                        bus_sch_adr <= "10";
                                        bus_sch_ss  <= boot_wd1;
                                    elsif bus_sch_adr = "10" then
                                        bus_sch_adr <= "11";
                                        bus_sch_ss  <= boot_wd1;
                                    elsif bus_sch_adr = "11" then
                                        bus_sch_st <= ack;
                                    end if;
                                end if;
                            end if;

                        when getx_msb =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '1';
                                i2c_addr_ptr <= "0010010"; -- Readout 12H
                                i2c_data_wr <= "00000000";
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= getx_lsb;
                                    data(15 downto 8) <= i2c_data_rd;
                                end if;
                            end if;

                        when getx_lsb =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '1';
                                i2c_addr_ptr <= "0010011"; -- Readout 13H
                                i2c_data_wr <= "00000000";
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= gety_msb;
                                    data(7 downto 0) <= i2c_data_rd;
                                end if;
                            end if;

                        when gety_msb =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '1';
                                i2c_addr_ptr <= "0010100"; -- Readout 14H
                                i2c_data_wr <= "00000000";
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= gety_lsb;
                                    data(35 downto 32) <= i2c_data_rd(7 downto 4);
                                    data(27 downto 24) <= i2c_data_rd(3 downto 0);
                                    data(31)           <= '0';
                                end if;
                            end if;

                        when gety_lsb =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '1';
                                i2c_addr_ptr <= "0010101";-- Readout 15H
                                i2c_data_wr <= "00000000";
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= getz_msb;
                                    data(23 downto 16) <= i2c_data_rd;
                                end if;
                            end if;

                        when getz_msb =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '1';
                                i2c_addr_ptr <= "0010110"; -- Readout 16H
                                i2c_data_wr <= "00000000";
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    load <= '0';
                                    bus_sch_ss <= getz_lsb;
                                    data(51 downto 44) <= i2c_data_rd;

                                end if;
                            end if;

                        when getz_lsb =>
                            if load = '0' then
                                i2c_en <= '1';
                                i2c_addr <= get_adr(bus_sch_adr);
                                i2c_rw <= '1';
                                i2c_addr_ptr <= "0010111"; -- Readout 17H
                                i2c_data_wr <= "00000000";
                                if i2c_busy = '1' and i2c_busy_prev = '0' then
                                    load <= '1';
                                end if;
                            else
                                i2c_en <= '0';
                                if i2c_data_v = '1' then
                                    data(43 downto 36) <= i2c_data_rd;
                                    case bus_sch_adr is
                                        when "00" => data(30 downto 28) <= pix1 (2 downto 0); data(62 downto 60) <= pix1(5 downto 3);
                                        when "01" => data(30 downto 28) <= pix2 (2 downto 0); data(62 downto 60) <= pix2(5 downto 3);
                                        when "10" => data(30 downto 28) <= pix3 (2 downto 0); data(62 downto 60) <= pix3(5 downto 3);
                                        when others => data(30 downto 28) <= pix4 (2 downto 0); data(62 downto 60) <= pix4(5 downto 3);
                                    end case;
                                    data(59 downto 52) <= timestamp_slv;
                                    data(63) <= '1';
                                    load <= '0';
                                    if bus_sch_adr = "00" then -- Move to next device on bus or send ack if done. Also provides data to FIFO
                                        bus_sch_adr <= "01";
                                        bus_sch_ss  <= getx_msb;
                                        data_ack <= '1';
                                    elsif bus_sch_adr = "01" then
                                        bus_sch_adr <= "10";
                                        bus_sch_ss  <= getx_msb;
                                        data_ack <= '1';
                                    elsif bus_sch_adr = "10" then
                                        bus_sch_adr <= "11";
                                        bus_sch_ss  <= getx_msb;
                                        data_ack <= '1';
                                    elsif bus_sch_adr = "11" then
                                        bus_sch_st <= ack;
                                        data_ack <= '1';
                                    end if;
                                end if;
                            end if;
                    end case;

                when ack =>
                    data_ack <= '0';
                    cmd_done <= '1'; -- Flag as completed
                    bus_sch_st <= idle;
            end case;
        end if;
    end process;
    

    i2c_busy_tracker : process (clk, reset) -- To check status of I2C master
    begin
        if reset = '1' then
            i2c_busy_prev <= '0';
        elsif rising_edge(clk) then
            i2c_busy_prev <= i2c_busy;
        end if;
    end process;
    i2c_master : i2c_master_ctrl 
    port map(
        clk => clk,
        reset => reset,
        scl => scl,
        sda => sda,
        ena => i2c_en,
        addr => i2c_addr,
        rw => i2c_rw,
        conv_trig => '0',
        addr_ptr => i2c_addr_ptr,
        data_wr => i2c_data_wr,
        busy => i2c_busy,
        data_rd => i2c_data_rd,
        data_rd_v => i2c_data_v,
        i2c_error => open,
        sda_en_n => sda_en_n,
        scl_en => scl_en
    );
end Behavioral;
