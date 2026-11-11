// Tests the same compiled Instruction object linked into Simulator.
#include "Instruction.h"
#include <iostream>
#include <stdexcept>
#include <cstdio>
void require(bool yes) { if(!yes) throw std::runtime_error("address contract mismatch"); }
int main() {
  size_t cases=0;
  for (uint64_t base : {0ULL,31ULL,0x100000000ULL,0x10000001fULL})
  for (uint64_t offset : {0ULL,1ULL,32ULL,0x80000001ULL})
  for (size_t bits : {1,4,8,16,32,64,128})
  for (size_t request : {16,32,64})
  for (int stride : {0,1,7,1024}) {
    Instruction inst(Opcode::MOVIN,0,0,base,{2,3},{stride,1},bits,{},{},{});
    inst.set_dram_element_offset(offset);
    std::set<addr_type> oracle;
    // Enumerate individual bits, independently of the implementation's intervals.
    for (uint64_t i=0;i<2;i++) for(uint64_t j=0;j<3;j++)
      for (uint64_t bit=0;bit<bits;bit++) {
        uint64_t byte=base+((offset+i*stride+j)*bits+bit)/8;
        oracle.insert((byte/request)*request);
      }
    require(*inst.get_dram_address(request)==oracle);
    require(inst.get_base_dram_address()==base+offset*bits/8);
    cases++;
  }
  Instruction indirect(Opcode::MOVIN,0,0,0x10000000,{3},{1},32,{},{},{});
  uint64_t indices[]={7,31,100};
  {std::ofstream f("indices.bin",std::ios::binary);f.write(reinterpret_cast<char*>(indices),sizeof(indices));}
  indirect.set_indirect_index_path("indices.bin");indirect.set_dram_element_offset(4);
  std::set<addr_type> expected;
  for (int i=0;i<3;i++) expected.insert((0x10000000+4*(4+i+indices[i]))/32*32);
  require(*indirect.get_dram_address(32)==expected);cases++;
  std::remove("indices.bin");
  bool raised=false;try{indirect.get_dram_address(32);}catch(const std::runtime_error&){raised=true;}
  require(raised);cases++;
  for (size_t request:{0,3}) {
    raised=false;try{indirect.get_dram_address(request);}catch(const std::invalid_argument&){raised=true;}
    require(raised);cases++;
  }
  std::cout << "{\"cases\":" << cases << ",\"failures\":0}" << std::endl;
}
