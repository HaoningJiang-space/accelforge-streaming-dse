"""Project native NVDLA dimensions into the STREAM/ZigZag topology schema."""

import yaml


def port(name, direction, bandwidth, allocations):
    return dict(name=name, type=direction, bandwidth_min=bandwidth,
                bandwidth_max=bandwidth, allocation=allocations)


def project(path, px, py, capacity):
    if min(px, py, capacity) <= 0:
        raise ValueError("array dimensions and SRAM capacity must be positive")
    core = dict(name="nvdla_geometry", type="zigzag.compute",
                operand_precision={"input": "int8", "accumulator": "int8"},
                operational_array=dict(unit_energy=0.084, unit_area=0, dimensions=["D1", "D2"], sizes=[px, py]))
    core["memories"] = {
        "weight_register": dict(size=8, r_cost=0, w_cost=0, area=0, latency=0,
                                operands=["I2"], served_dimensions=[], auto_cost_extraction=False,
                                ports=[port("r_port_1", "read", 8, ["I2, tl"]),
                                       port("w_port_1", "write", 8, ["I2, fh"])]),
        "global_buffer": dict(size=capacity * 8, r_cost=0.249 * 4096, w_cost=0.293 * 1024, area=0, latency=1,
                              operands=["I1", "I2", "O"], served_dimensions=["D1", "D2"],
                              auto_cost_extraction=False,
                              ports=[port("r_port_1", "read", 4096, ["I1, tl", "I2, tl", "O, tl", "O, th"]),
                                     port("w_port_1", "write", 1024, ["I1, fh", "I2, fh", "O, fh", "O, fl"])])}
    arch = dict(name="nvdla_geometry", cores={0: "core.yaml"}, unit_energy_cost=0,
                memories={
                    "gb": dict(offchip=False, views=["0.global_buffer"],
                               ports={"read": {"from": "r_port_1", "cores": [0]},
                                      "write": {"from": "w_port_1", "cores": [0]}}),
                    "dram": dict(offchip=True, views=[], capacity_bits=10_000_000_000,
                                 ports={"rw": dict(bandwidth=307.2, serves={"any": ["read", "write"]},
                                                   read_energy=7.03, write_energy=7.03)})},
                connections=[dict(type="bus", ends={"gb": ["read", "write"], "dram": ["rw"]},
                                  bandwidth=307.2)])
    (path / "core.yaml").write_text(yaml.safe_dump(core, sort_keys=False), encoding="utf-8")
    spec = path / "nvdla_geometry.yaml"
    spec.write_text(yaml.safe_dump(arch, sort_keys=False), encoding="utf-8")
    return spec
