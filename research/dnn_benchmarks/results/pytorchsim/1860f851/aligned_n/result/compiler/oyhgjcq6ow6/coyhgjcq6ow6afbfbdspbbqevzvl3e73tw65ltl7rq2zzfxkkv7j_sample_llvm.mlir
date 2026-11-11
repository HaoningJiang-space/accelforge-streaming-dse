module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<16 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<256 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<256 x f32>>
  llvm.func @kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: !llvm.ptr, %arg6: !llvm.ptr, %arg7: i64, %arg8: i64, %arg9: i64, %arg10: !llvm.ptr, %arg11: !llvm.ptr, %arg12: i64, %arg13: i64, %arg14: i64) {
    %0 = llvm.mlir.constant(2 : index) : i64
    %1 = llvm.mlir.constant(256 : index) : i64
    %2 = llvm.mlir.constant(16 : index) : i64
    %3 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %4 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %5 = llvm.mlir.constant(0 : index) : i64
    %6 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %7 = llvm.mlir.constant(3735928559 : index) : i64
    %8 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %9 = llvm.mlir.constant(8 : index) : i64
    %10 = llvm.mlir.constant(0 : index) : i64
    %11 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %12 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %13 = llvm.mlir.constant(8 : i64) : i64
    %14 = llvm.mlir.constant(dense<0.000000e+00> : vector<32xf32>) : vector<32xf32>
    %15 = llvm.mlir.constant(16 : index) : i64
    %16 = llvm.mlir.constant(1 : index) : i64
    %17 = llvm.mlir.constant(256 : index) : i64
    %18 = llvm.getelementptr %8[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<16 x f32>>
    %19 = llvm.inttoptr %7 : i64 to !llvm.ptr<1>
    %20 = llvm.insertvalue %19, %6[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %18, %20[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %5, %21[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %15, %22[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = llvm.insertvalue %15, %23[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %25 = llvm.insertvalue %15, %24[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %26 = llvm.insertvalue %16, %25[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %27 = llvm.getelementptr %4[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<256 x f32>>
    %28 = llvm.inttoptr %7 : i64 to !llvm.ptr<1>
    %29 = llvm.insertvalue %28, %6[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = llvm.insertvalue %27, %29[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.insertvalue %5, %30[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %32 = llvm.insertvalue %15, %31[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %33 = llvm.insertvalue %17, %32[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %34 = llvm.insertvalue %17, %33[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.insertvalue %16, %34[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %36 = llvm.getelementptr %3[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<256 x f32>>
    %37 = llvm.inttoptr %7 : i64 to !llvm.ptr<1>
    %38 = llvm.insertvalue %37, %6[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %36, %38[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.insertvalue %5, %39[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.insertvalue %15, %40[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.insertvalue %17, %41[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.insertvalue %17, %42[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.insertvalue %16, %43[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%10 : i64)
  ^bb1(%45: i64):  // 2 preds: ^bb0, ^bb11
    %46 = llvm.icmp "slt" %45, %2 : i64
    llvm.cond_br %46, ^bb2, ^bb12
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%10 : i64)
  ^bb3(%47: i64):  // 2 preds: ^bb2, ^bb10
    %48 = llvm.icmp "slt" %47, %1 : i64
    llvm.cond_br %48, ^bb4, ^bb11
  ^bb4:  // pred: ^bb3
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "VectorCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %49 = llvm.extractvalue %44[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.mlir.constant(256 : index) : i64
    %51 = llvm.mul %10, %50 : i64
    %52 = llvm.add %51, %10 : i64
    %53 = llvm.getelementptr %49[%52] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %14, %53 {alignment = 4 : i64} : vector<32xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.br ^bb5(%10 : i64)
  ^bb5(%54: i64):  // 2 preds: ^bb4, ^bb9
    %55 = llvm.icmp "slt" %54, %2 : i64
    llvm.cond_br %55, ^bb6, ^bb10
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%10 : i64)
  ^bb7(%56: i64):  // 2 preds: ^bb6, ^bb8
    %57 = llvm.icmp "slt" %56, %0 : i64
    llvm.cond_br %57, ^bb8, ^bb9
  ^bb8:  // pred: ^bb7
    %58 = llvm.mul %56, %2 : i64
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulPreload"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %59 = llvm.mlir.constant(1 : index) : i64
    %60 = llvm.mlir.constant(256 : index) : i64
    %61 = llvm.sub %60, %58 : i64
    %62 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %63 = llvm.trunc %61 : i64 to i32
    %64 = llvm.mlir.undef : vector<8xi32>
    %65 = llvm.mlir.constant(0 : i32) : i32
    %66 = llvm.insertelement %63, %64[%65 : i32] : vector<8xi32>
    %67 = llvm.shufflevector %66, %64 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %68 = llvm.icmp "sgt" %67, %62 : vector<8xi32>
    %69 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %70 = llvm.extractvalue %35[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.mlir.constant(256 : index) : i64
    %72 = llvm.mul %10, %71 : i64
    %73 = llvm.add %72, %58 : i64
    %74 = llvm.getelementptr %70[%73] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %75 = llvm.intr.masked.load %74, %68, %69 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    "vcix.iv"(%75, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %76 = llvm.mul %56, %2 : i64
    %77 = llvm.add %76, %9 : i64
    %78 = llvm.mlir.constant(1 : index) : i64
    %79 = llvm.mlir.constant(256 : index) : i64
    %80 = llvm.sub %79, %77 : i64
    %81 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %82 = llvm.trunc %80 : i64 to i32
    %83 = llvm.mlir.undef : vector<8xi32>
    %84 = llvm.mlir.constant(0 : i32) : i32
    %85 = llvm.insertelement %82, %83[%84 : i32] : vector<8xi32>
    %86 = llvm.shufflevector %85, %83 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %87 = llvm.icmp "sgt" %86, %81 : vector<8xi32>
    %88 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %89 = llvm.extractvalue %35[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %90 = llvm.mlir.constant(256 : index) : i64
    %91 = llvm.mul %10, %90 : i64
    %92 = llvm.add %91, %77 : i64
    %93 = llvm.getelementptr %89[%92] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %94 = llvm.intr.masked.load %93, %87, %88 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    "vcix.iv"(%94, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%12, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %95 = llvm.extractvalue %26[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %96 = llvm.mlir.constant(16 : index) : i64
    %97 = llvm.mul %10, %96 : i64
    %98 = llvm.add %97, %10 : i64
    %99 = llvm.getelementptr %95[%98] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %100 = llvm.load %99 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    "vcix.iv"(%100, %13) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %101 = llvm.extractvalue %26[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %102 = llvm.mlir.constant(16 : index) : i64
    %103 = llvm.mul %10, %102 : i64
    %104 = llvm.add %103, %9 : i64
    %105 = llvm.getelementptr %101[%104] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %106 = llvm.load %105 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%106, %13) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%13) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %107 = "vcix.v.i"(%13) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %108 = llvm.mul %56, %2 : i64
    %109 = llvm.mlir.constant(1 : index) : i64
    %110 = llvm.mlir.constant(256 : index) : i64
    %111 = llvm.sub %110, %108 : i64
    %112 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %113 = llvm.trunc %111 : i64 to i32
    %114 = llvm.mlir.undef : vector<8xi32>
    %115 = llvm.mlir.constant(0 : i32) : i32
    %116 = llvm.insertelement %113, %114[%115 : i32] : vector<8xi32>
    %117 = llvm.shufflevector %116, %114 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %118 = llvm.icmp "sgt" %117, %112 : vector<8xi32>
    %119 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %120 = llvm.extractvalue %44[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %121 = llvm.mlir.constant(256 : index) : i64
    %122 = llvm.mul %10, %121 : i64
    %123 = llvm.add %122, %108 : i64
    %124 = llvm.getelementptr %120[%123] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %125 = llvm.intr.masked.load %124, %118, %119 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    %126 = llvm.fadd %125, %107  : vector<8xf32>
    %127 = llvm.mlir.constant(1 : index) : i64
    %128 = llvm.mlir.constant(256 : index) : i64
    %129 = llvm.sub %128, %108 : i64
    %130 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %131 = llvm.trunc %129 : i64 to i32
    %132 = llvm.mlir.undef : vector<8xi32>
    %133 = llvm.mlir.constant(0 : i32) : i32
    %134 = llvm.insertelement %131, %132[%133 : i32] : vector<8xi32>
    %135 = llvm.shufflevector %134, %132 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %136 = llvm.icmp "sgt" %135, %130 : vector<8xi32>
    %137 = llvm.extractvalue %44[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %138 = llvm.mlir.constant(256 : index) : i64
    %139 = llvm.mul %10, %138 : i64
    %140 = llvm.add %139, %108 : i64
    %141 = llvm.getelementptr %137[%140] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.intr.masked.store %126, %141, %136 {alignment = 4 : i32} : vector<8xf32>, vector<8xi1> into !llvm.ptr<1>
    %142 = "vcix.v.i"(%13) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %143 = llvm.mul %56, %2 : i64
    %144 = llvm.add %143, %9 : i64
    %145 = llvm.mlir.constant(1 : index) : i64
    %146 = llvm.mlir.constant(256 : index) : i64
    %147 = llvm.sub %146, %144 : i64
    %148 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %149 = llvm.trunc %147 : i64 to i32
    %150 = llvm.mlir.undef : vector<8xi32>
    %151 = llvm.mlir.constant(0 : i32) : i32
    %152 = llvm.insertelement %149, %150[%151 : i32] : vector<8xi32>
    %153 = llvm.shufflevector %152, %150 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %154 = llvm.icmp "sgt" %153, %148 : vector<8xi32>
    %155 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %156 = llvm.extractvalue %44[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %157 = llvm.mlir.constant(256 : index) : i64
    %158 = llvm.mul %10, %157 : i64
    %159 = llvm.add %158, %144 : i64
    %160 = llvm.getelementptr %156[%159] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %161 = llvm.intr.masked.load %160, %154, %155 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    %162 = llvm.fadd %161, %142  : vector<8xf32>
    %163 = llvm.mlir.constant(1 : index) : i64
    %164 = llvm.mlir.constant(256 : index) : i64
    %165 = llvm.sub %164, %144 : i64
    %166 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %167 = llvm.trunc %165 : i64 to i32
    %168 = llvm.mlir.undef : vector<8xi32>
    %169 = llvm.mlir.constant(0 : i32) : i32
    %170 = llvm.insertelement %167, %168[%169 : i32] : vector<8xi32>
    %171 = llvm.shufflevector %170, %168 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %172 = llvm.icmp "sgt" %171, %166 : vector<8xi32>
    %173 = llvm.extractvalue %44[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %174 = llvm.mlir.constant(256 : index) : i64
    %175 = llvm.mul %10, %174 : i64
    %176 = llvm.add %175, %144 : i64
    %177 = llvm.getelementptr %173[%176] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.intr.masked.store %162, %177, %172 {alignment = 4 : i32} : vector<8xf32>, vector<8xi1> into !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %178 = llvm.add %56, %0 : i64
    llvm.br ^bb7(%178 : i64)
  ^bb9:  // pred: ^bb7
    %179 = llvm.add %54, %2 : i64
    llvm.br ^bb5(%179 : i64)
  ^bb10:  // pred: ^bb5
    %180 = llvm.add %47, %1 : i64
    llvm.br ^bb3(%180 : i64)
  ^bb11:  // pred: ^bb3
    %181 = llvm.add %45, %2 : i64
    llvm.br ^bb1(%181 : i64)
  ^bb12:  // pred: ^bb1
    llvm.return
  }
  llvm.func @wrapper_kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: !llvm.ptr, %arg6: !llvm.ptr, %arg7: i64, %arg8: i64, %arg9: i64, %arg10: !llvm.ptr, %arg11: !llvm.ptr, %arg12: i64, %arg13: i64, %arg14: i64) {
    %0 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %1 = llvm.insertvalue %arg10, %0[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %2 = llvm.insertvalue %arg11, %1[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %3 = llvm.insertvalue %arg12, %2[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %4 = llvm.insertvalue %arg13, %3[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %5 = llvm.insertvalue %arg14, %4[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %6 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %7 = llvm.insertvalue %arg5, %6[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %8 = llvm.insertvalue %arg6, %7[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %9 = llvm.insertvalue %arg7, %8[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %10 = llvm.insertvalue %arg8, %9[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %11 = llvm.insertvalue %arg9, %10[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %12 = llvm.mlir.undef : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)>
    %13 = llvm.insertvalue %arg0, %12[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %14 = llvm.insertvalue %arg1, %13[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %15 = llvm.insertvalue %arg2, %14[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %16 = llvm.insertvalue %arg3, %15[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %17 = llvm.insertvalue %arg4, %16[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %18 = llvm.extractvalue %17[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %19 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %20 = llvm.extractvalue %17[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %21 = llvm.extractvalue %17[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %22 = llvm.extractvalue %17[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %23 = llvm.extractvalue %11[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %24 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %25 = llvm.extractvalue %11[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %26 = llvm.extractvalue %11[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %27 = llvm.extractvalue %11[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %28 = llvm.extractvalue %5[0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %29 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %30 = llvm.extractvalue %5[2] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %31 = llvm.extractvalue %5[3, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %32 = llvm.extractvalue %5[4, 0] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    llvm.call @kernel(%18, %19, %20, %21, %22, %23, %24, %25, %26, %27, %28, %29, %30, %31, %32) : (!llvm.ptr, !llvm.ptr, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64, !llvm.ptr, !llvm.ptr, i64, i64, i64) -> ()
    llvm.return
  }
}

