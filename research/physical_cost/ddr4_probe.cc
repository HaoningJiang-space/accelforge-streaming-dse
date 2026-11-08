// Standalone harness for the pinned CACTI external I/O model.
#include "extio.h"
#include <cstdlib>
#include <iomanip>
#include <iostream>

// The rest of CACTI is unnecessary. Initialize every field used by Extio and
// the DDR4 IOTechParam constructor below.
InputParameter::InputParameter() {}
InputParameter *g_ip;
Component::Component() : delay(0) {}
Component::~Component() {}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    const int lanes = std::atoi(argv[1]);
    const int clock_mhz = std::atoi(argv[2]);
    if (lanes < 8 || lanes % 8 || clock_mhz <= 0) return 2;

    InputParameter input;
    g_ip = &input;
    input.io_type = DDR4;
    input.num_dq = lanes;
    input.num_dqs = lanes / 4;
    input.num_ca = 24;
    input.num_clk = 2;
    input.num_mem_dq = 1;
    input.mem_data_width = 8;
    input.ron_value = 34;
    input.rtt_value = 60;
    input.tflight_value = 0.5;
    input.addr_timing = 1;
    input.duty_cycle = 1;
    input.activity_dq = 0.5;
    input.activity_ca = 0.25;
    // One loaded rank, host-DIMM topology, one byte per DRAM chip.
    IOTechParam params(&input, DDR4, 1, 8, lanes, 1, 1, clock_mhz);
    Extio io(&params);
    std::cout << std::setprecision(12);
    io.extio_area();
    for (auto state : {READ, WRITE, IDLE}) {
        input.iostate = state;
        io.extio_power_dynamic();
        io.extio_power_term();
        io.extio_power_phy();
    }
}
