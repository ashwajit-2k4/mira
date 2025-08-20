------------------------------------------------------------------------
-- Author      : Suchet Gopal
-- Description : Synchronous MUX that merges 16 + 1 (ACK) streams to 1 FIFO. If multiple streams
--               have data, their packets are latched in and sent out sequentially
------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity data_merge is
    port (
        clk          : in  std_logic;
        reset        : in  std_logic; 
		  data_in_v_comm : in std_logic;
        data_in_v_0  : in  std_logic;              -- Input valid signal
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
		  
		  data_in_comm : in  std_logic_vector(63 downto 0);
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
end entity;

architecture Behavioral of data_merge is

    
    constant NUM_INPUTS : integer := 17;

    type stdl_array is array (0 to NUM_INPUTS-1) of std_logic;
    type data_array is array (0 to NUM_INPUTS-1) of std_logic_vector(63 downto 0);

    signal in_valid, in_valid_latch, in_valid_ack : stdl_array;
    signal data_in, data_buf : data_array;

    signal out_data_reg  : std_logic_vector(63 downto 0) := (others => '0');
    signal out_valid_reg : std_logic := '0';

    signal selected_data : std_logic_vector(63 downto 0) := (others => '0');
    signal data_selected : std_logic := '0';

begin

    -- Map input valid signals
    in_valid(0)  <= data_in_v_comm;
    in_valid(1)  <= data_in_v_0;
    in_valid(2)  <= data_in_v_1;
    in_valid(3)  <= data_in_v_2;
    in_valid(4)  <= data_in_v_3;
    in_valid(5)  <= data_in_v_4;
    in_valid(6)  <= data_in_v_5;
    in_valid(7)  <= data_in_v_6;
    in_valid(8)  <= data_in_v_7;
    in_valid(9)  <= data_in_v_8;
    in_valid(10) <= data_in_v_9;
    in_valid(11) <= data_in_v_10;
    in_valid(12) <= data_in_v_11;
    in_valid(13) <= data_in_v_12;
    in_valid(14) <= data_in_v_13;
    in_valid(15) <= data_in_v_14;
    in_valid(16) <= data_in_v_15;

    -- Map input data
    data_in(0)  <= data_in_comm;
    data_in(1)  <= data_in_0;
    data_in(2)  <= data_in_1;
    data_in(3)  <= data_in_2;
    data_in(4)  <= data_in_3;
    data_in(5)  <= data_in_4;
    data_in(6)  <= data_in_5;
    data_in(7)  <= data_in_6;
    data_in(8)  <= data_in_7;
    data_in(9)  <= data_in_8;
    data_in(10) <= data_in_9;
    data_in(11) <= data_in_10;
    data_in(12) <= data_in_11;
    data_in(13) <= data_in_12;
    data_in(14) <= data_in_13;
    data_in(15) <= data_in_14;
    data_in(16) <= data_in_15;

    process(clk, reset)
        variable found_valid : boolean;
    begin
        if reset = '1' then
            
        elsif rising_edge(clk) then
            for i in 0 to NUM_INPUTS-1 loop -- Go through inputs and latch if data is available
 
                if in_valid_latch(i) = '0' then
                    if in_valid(i) = '1' then
                        in_valid_latch(i) <= '1';
                        data_buf(i)       <= data_in(i);
                    else 
                        in_valid_latch(i) <= '0';
                    end if;
                elsif in_valid_latch(i) = '1' and in_valid_ack(i) = '1' then -- Mark data as read
                    in_valid_latch(i) <= '0';
                end if;
            end loop;
            in_valid_ack  <= (others => '0');
            out_valid_reg <= '0';
            found_valid := false;
            for i in 0 to NUM_INPUTS-1 loop
                if in_valid_latch(i) = '1' and in_valid_ack(i) = '0' and not found_valid then -- Find a waiting packet. 
                    in_valid_ack(i) <= '1';
                    out_valid_reg   <= '1';
                    out_data_reg    <= data_buf(i);
                    found_valid     := true;
                end if;
            end loop;

        end if;
    end process;

    -- Output connections
    data_out_v <= out_valid_reg;
    data_out   <= out_data_reg;

end architecture;
