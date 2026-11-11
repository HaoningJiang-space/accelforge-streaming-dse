
// GEMM   kernel
// M = 3136
// N = 256
// K = 64
// TILE_M = 3200
// TILE_N = 256
// TILE_K = 64
// SUB_TILE_M = 3200
// SUB_TILE_N = 256
memref.global @X_spad : memref<3200x64xf32, 1>
memref.global @W_spad : memref<64x256xf32, 1>
memref.global @Y_spad : memref<3200x256xf32, 1>
#t_map0 = affine_map<(d0, d1) -> (256*d0 + d1)>
#t_map1 = affine_map<(d0, d1) -> (64*d0 + d1)>

func.func @kernel(%X: memref<200704xf32>, %W: memref<16384xf32>, %Y: memref<802816xf32>) {
  %X_buffer = memref.get_global @X_spad : memref<3200x64xf32, 1>
  %W_buffer = memref.get_global @W_spad : memref<64x256xf32, 1>
  %Y_buffer = memref.get_global @Y_spad : memref<3200x256xf32, 1>

  %v0 = arith.constant dense<0.0> : vector<6400xf32>
  %t_const0 = arith.constant 0 : index
  %t_const1 = arith.constant 1 : index
  %t_const2 = arith.constant 3 : index
  %t_const3 = arith.constant 2 : index
  %t_alloc0 = memref.alloc() : memref<1xi32> // 0
  %t_alloc1 = memref.alloc() : memref<1xi32> // 1
  %t_alloc2 = memref.alloc() : memref<1xi32> // 2
  affine.for %index0 = 0 to 3136 step 3200 {
    affine.for %index1 = 0 to 256 step 256 {
      affine.vector_store %v0, %Y_buffer[0, 0] : memref<3200x256xf32, 1>, vector<6400xf32>
      affine.for %index2 = 0 to 64 step 64 {
        %apply0 = affine.apply #t_map1(%index0, %index2)
        memref.dma_start %X[%apply0], %X_buffer[%t_const0, %t_const0], %t_const3, %t_alloc1[%t_const0], %t_const1, %t_const1 : memref<200704xf32>, memref<3200x64xf32, 1>, memref<1xi32> {dram_stride = [64, 1], sram_stride = [1, 3200], padding = 0, subtile_size = [3200, 64], async = 1 : i64}
        %apply1 = affine.apply #t_map0(%index2, %index1)
        memref.dma_start %W[%apply1], %W_buffer[%t_const0, %t_const0], %t_const3, %t_alloc2[%t_const0], %t_const1, %t_const1 : memref<16384xf32>, memref<64x256xf32, 1>, memref<1xi32> {dram_stride = [256, 1], sram_stride = [1, 64], padding = 0, subtile_size = [64, 256], async = 1 : i64}
        linalg.matmul ins(%X_buffer, %W_buffer : memref<3200x64xf32, 1>, memref<64x256xf32, 1>)
                outs(%Y_buffer : memref<3200x256xf32, 1>)
      } { accumulation_loop=true, subtile_loop="k" }
      affine.for %compute_idx = 0 to 1 step 1
      {
      } {inner_loop=false}
      %epilogue_apply0 = affine.apply #t_map0(%index0, %index1)
      memref.dma_start %Y_buffer[%t_const0, %t_const0], %Y[%epilogue_apply0], %t_const2, %t_alloc0[%t_const0], %t_const1, %t_const1 : memref<3200x256xf32, 1>, memref<802816xf32>, memref<1xi32> {dram_stride = [256, 1], sram_stride = [1, 3200], padding = 0}
    } { outer_loop=true, subtile_loop="n"  }
  } { outer_loop=true, subtile_loop="m" }
  return
}
