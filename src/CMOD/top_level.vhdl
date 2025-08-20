-- Top Level entity for interconnecting all components
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity top_level is
    Port (
        sys_clk     : in    STD_LOGIC;
        reset       : in    STD_LOGIC;
        rst_status  : out   STD_LOGIC;
        spi_miso    : out   STD_LOGIC; -- SPI Bus Signals
        spi_mosi    : in    STD_LOGIC;
        spi_clk     : in    STD_LOGIC;
        spi_cs      : in    STD_LOGIC;
        scl         : inout STD_LOGIC_VECTOR (15 downto 0); -- I2C and interrupt signals
        sda         : inout STD_LOGIC_VECTOR (15 downto 0);
        int         : out   STD_LOGIC_VECTOR (7 downto 0)
    );
end top_level;

architecture Behavioral of top_level is

    component spi_slave is
        port (
           clk        : in  STD_LOGIC;
           reset      : in  STD_LOGIC;                                       
           miso       : out STD_LOGIC;
           miso_en    : out STD_LOGIC;
           mosi       : in  STD_LOGIC;	                                        
           sclk       : in  STD_LOGIC;
           ss         : in  STD_LOGIC;
           data_in_v  : in  STD_LOGIC;
           data_in    : in  STD_LOGIC_VECTOR(63 downto 0);
           data_out   : out STD_LOGIC_VECTOR(63 downto 0);
           data_out_v : out STD_LOGIC;
           data_in_ready   : out STD_LOGIC
    
        );
    end component;
    
    component clk_wiz_0 -- MMCM Instantation
        port (
            clk_in1  : in  std_logic;
            clk_out1 : out std_logic;
            reset    : in  std_logic;
            locked   : out std_logic
        );
    end component;

    component tmag_scheduling_core is 
    port (
        clk         : in  STD_LOGIC;
        reset       : in  STD_LOGIC;
        comm_in     : in  STD_LOGIC_VECTOR (7 downto 0);
        comm_in_v   : in  STD_LOGIC;
        frame_out   : out STD_LOGIC_VECTOR (63 downto 0);
        frame_out_v : out STD_LOGIC;
        scl         : in  STD_LOGIC_VECTOR (15 downto 0);
        sda         : in  STD_LOGIC_VECTOR (15 downto 0);
        scl_en      : out STD_LOGIC_VECTOR (15 downto 0);
        sda_en_n    : out STD_LOGIC_VECTOR (15 downto 0)

    );
    end component;

    component fifo
   
    port (
		clock : in STD_LOGIC;
        data_in : in STD_LOGIC_VECTOR(63 downto 0);     -- Data coming in to FIFO
        clear : in STD_LOGIC;														  -- Clears FIFO and resets head and tail to beginning
        wr_en : in STD_LOGIC;														  -- Write enable, controlled by the module to which data is being sent
		rd_en : in STD_LOGIC; 													  -- Read enable, controlled by module from which data is acquired
        data_out : out STD_LOGIC_VECTOR(63 downto 0) := (others => '0');    -- Output
		fifo_full : out STD_LOGIC := '0';								-- Active high
		fifo_empty : out STD_LOGIC := '1'
    );
    end component;

    component tx_packetise is -- Not used in final version
        port (
            clk          : in  std_logic;
            reset        : in  std_logic;             
            data_in_v    : in  std_logic;              -- Input valid signal
            data_in      : in  std_logic_vector(63 downto 0); -- 64-bit input data
            in_ready     : out std_logic;              -- Input ready signal
    
            data_out_v   : out std_logic;              -- Output valid signal
            data_out     : out std_logic_vector(31 downto 0); -- 8-bit output data
            out_ready    : in  std_logic               -- Output ready signal
        );
    end component;
    
    signal clk, clk_locked : STD_LOGIC;
    signal miso_buff, miso_en : STD_LOGIC;
    signal sda_en_n, scl_en : STD_LOGIC_VECTOR (15 downto 0);
    signal sch_data_out, fifo_data_out : STD_LOGIC_VECTOR (63 downto 0);
    signal spi_tx_packet, data_with_parity : STD_LOGIC_VECTOR (63 downto 0);
    signal spi_rx_packet : STD_LOGIC_VECTOR (63 downto 0);
    signal spi_ack, spi_rx_v, spi_tx_v, sch_data_v, fifo_full, fifo_empty : STD_LOGIC;
    signal tx_pack_in_v, tx_pack_out_v, tx_pack_in_ready, tx_pack_out_ready : STD_LOGIC;

    function xor_reduce(vec: std_logic_vector) return std_logic is -- XOR_REDUCE FUNC. for parity bit calc.
    variable result : std_logic := '0';
    begin
        for i in vec'range loop
            result := result xor vec(i);
        end loop;
        return result;
    end function xor_reduce;
    

begin
  clk_inst : clk_wiz_0
  port map (
    clk_in1  => sys_clk,
    clk_out1 => clk,
    reset    => reset,
    locked   => clk_locked
   );

   spi_inst: spi_slave 
   port map(
        clk => clk,
        reset => reset,
        miso => miso_buff,
        miso_en => miso_en,
        mosi => spi_mosi,
        sclk => spi_clk,
        ss   => spi_cs,
        data_in_v  => spi_tx_v,
        data_in    => data_with_parity,
        data_out_v => spi_rx_v,
        data_out   => spi_rx_packet,
        data_in_ready => spi_ack                  

   );

    data_fifo_0 : fifo 
    port map(
        clock => clk,
        clear => reset,
        data_in => sch_data_out,
        wr_en =>  sch_data_v,
        rd_en => spi_ack,
        data_out => spi_tx_packet,
        fifo_full => fifo_full,
        fifo_empty => fifo_empty
    );

    sch_core : tmag_scheduling_core 
    port map(
        clk => clk,
        reset => reset,
        comm_in => spi_rx_packet(7 downto 0),
        comm_in_v => spi_rx_v,
        frame_out => sch_data_out,
        frame_out_v => sch_data_v,
        scl => scl,
        sda => sda,
        sda_en_n => sda_en_n,
        scl_en   => scl_en
    );




    spi_miso <= miso_buff when miso_en = '1' else 'Z';
    spi_tx_v <= not(fifo_empty);
 

    gen_i2c_drive : for i in 0 to 15 generate -- For I2C Bus Outputs
    begin
        scl(i) <= '0' when scl_en(i)   = '1' else 'Z';
        sda(i) <= '0' when sda_en_n(i) = '0' else 'Z';
    end generate gen_i2c_drive;

    int <= (others => 'Z'); -- Not used in this project, set as 'Z'
    rst_status <= reset; -- Reset LED Indicator
    data_with_parity <= spi_tx_packet(63 downto 32) & (xor_reduce(spi_tx_packet)) & spi_tx_packet(30 downto 0);

end Behavioral;
-- Additional logic or signals can be added here if needed