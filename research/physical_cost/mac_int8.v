// One registered INT8 PE with a product pipeline and a signed 32-bit accumulator.
module mac_int8(
    input wire clk,
    input wire clear,
    input wire signed [7:0] x,
    input wire signed [7:0] y,
    output reg signed [31:0] accumulator
);
    reg signed [7:0] x_q, y_q;
    reg signed [15:0] product_q;
    always @(posedge clk) begin
        x_q <= x;
        y_q <= y;
        product_q <= x_q * y_q;
        if (clear)
            accumulator <= {{16{product_q[15]}}, product_q};
        else
            accumulator <= accumulator + product_q;
    end
endmodule
