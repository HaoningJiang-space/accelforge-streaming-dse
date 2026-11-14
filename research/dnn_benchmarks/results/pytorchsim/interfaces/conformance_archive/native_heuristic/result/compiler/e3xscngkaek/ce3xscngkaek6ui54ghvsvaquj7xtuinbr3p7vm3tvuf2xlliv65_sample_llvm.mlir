module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<64 x array<32 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<32 x array<128 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<64 x array<128 x f32>>
  llvm.func @kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: !llvm.ptr, %arg6: !llvm.ptr, %arg7: i64, %arg8: i64, %arg9: i64, %arg10: !llvm.ptr, %arg11: !llvm.ptr, %arg12: i64, %arg13: i64, %arg14: i64) {
    %0 = llvm.mlir.constant(128 : index) : i64
    %1 = llvm.mlir.constant(64 : index) : i64
    %2 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %3 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %4 = llvm.mlir.constant(128 : index) : i64
    %5 = llvm.mlir.constant(0 : index) : i64
    %6 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %7 = llvm.mlir.constant(3735928559 : index) : i64
    %8 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %9 = llvm.mlir.constant(56 : index) : i64
    %10 = llvm.mlir.constant(48 : index) : i64
    %11 = llvm.mlir.constant(40 : index) : i64
    %12 = llvm.mlir.constant(32 : index) : i64
    %13 = llvm.mlir.constant(1 : index) : i64
    %14 = llvm.mlir.constant(24 : index) : i64
    %15 = llvm.mlir.constant(16 : index) : i64
    %16 = llvm.mlir.constant(8 : index) : i64
    %17 = llvm.mlir.constant(0 : index) : i64
    %18 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %19 = llvm.mlir.constant(8 : i64) : i64
    %20 = llvm.mlir.constant(dense<0.000000e+00> : vector<64xf32>) : vector<64xf32>
    %21 = llvm.mlir.constant(64 : index) : i64
    %22 = llvm.mlir.constant(32 : index) : i64
    %23 = llvm.mlir.constant(1 : index) : i64
    %24 = llvm.getelementptr %8[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<64 x array<32 x f32>>
    %25 = llvm.inttoptr %7 : i64 to !llvm.ptr<1>
    %26 = llvm.insertvalue %25, %6[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %27 = llvm.insertvalue %24, %26[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %28 = llvm.insertvalue %5, %27[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %29 = llvm.insertvalue %21, %28[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = llvm.insertvalue %22, %29[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.insertvalue %22, %30[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %32 = llvm.insertvalue %23, %31[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %33 = llvm.getelementptr %3[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<32 x array<128 x f32>>
    %34 = llvm.inttoptr %7 : i64 to !llvm.ptr<1>
    %35 = llvm.insertvalue %34, %6[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %36 = llvm.insertvalue %33, %35[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.insertvalue %5, %36[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %38 = llvm.insertvalue %22, %37[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %4, %38[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.insertvalue %4, %39[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.insertvalue %23, %40[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.getelementptr %2[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<64 x array<128 x f32>>
    %43 = llvm.inttoptr %7 : i64 to !llvm.ptr<1>
    %44 = llvm.insertvalue %43, %6[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %42, %44[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.insertvalue %5, %45[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.insertvalue %21, %46[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = llvm.insertvalue %4, %47[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %49 = llvm.insertvalue %4, %48[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.insertvalue %23, %49[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%17 : i64)
  ^bb1(%51: i64):  // 2 preds: ^bb0, ^bb8
    %52 = llvm.icmp "slt" %51, %1 : i64
    llvm.cond_br %52, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%17 : i64)
  ^bb3(%53: i64):  // 2 preds: ^bb2, ^bb7
    %54 = llvm.icmp "slt" %53, %0 : i64
    llvm.cond_br %54, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "VectorCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %55 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.mlir.constant(128 : index) : i64
    %57 = llvm.mul %17, %56 : i64
    %58 = llvm.add %57, %17 : i64
    %59 = llvm.getelementptr %55[%58] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %20, %59 {alignment = 4 : i64} : vector<64xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.br ^bb5(%17 : i64)
  ^bb5(%60: i64):  // 2 preds: ^bb4, ^bb6
    %61 = llvm.icmp "slt" %60, %12 : i64
    llvm.cond_br %61, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulPreload"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %62 = llvm.extractvalue %41[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.mlir.constant(128 : index) : i64
    %64 = llvm.mul %17, %63 : i64
    %65 = llvm.add %64, %17 : i64
    %66 = llvm.getelementptr %62[%65] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %67 = llvm.load %66 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%67, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %68 = llvm.extractvalue %41[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.mlir.constant(128 : index) : i64
    %70 = llvm.mul %17, %69 : i64
    %71 = llvm.add %70, %16 : i64
    %72 = llvm.getelementptr %68[%71] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %73 = llvm.load %72 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%73, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %74 = llvm.extractvalue %41[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.mlir.constant(128 : index) : i64
    %76 = llvm.mul %17, %75 : i64
    %77 = llvm.add %76, %15 : i64
    %78 = llvm.getelementptr %74[%77] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %79 = llvm.load %78 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%79, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %80 = llvm.extractvalue %41[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %81 = llvm.mlir.constant(128 : index) : i64
    %82 = llvm.mul %17, %81 : i64
    %83 = llvm.add %82, %14 : i64
    %84 = llvm.getelementptr %80[%83] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %85 = llvm.load %84 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%85, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%18, %19) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %86 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %87 = llvm.mlir.constant(32 : index) : i64
    %88 = llvm.mul %17, %87 : i64
    %89 = llvm.add %88, %17 : i64
    %90 = llvm.getelementptr %86[%89] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %91 = llvm.load %90 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    "vcix.iv"(%91, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %92 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %93 = llvm.mlir.constant(32 : index) : i64
    %94 = llvm.mul %17, %93 : i64
    %95 = llvm.add %94, %16 : i64
    %96 = llvm.getelementptr %92[%95] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %97 = llvm.load %96 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%97, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %98 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %99 = llvm.mlir.constant(32 : index) : i64
    %100 = llvm.mul %17, %99 : i64
    %101 = llvm.add %100, %15 : i64
    %102 = llvm.getelementptr %98[%101] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %103 = llvm.load %102 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%103, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %104 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %105 = llvm.mlir.constant(32 : index) : i64
    %106 = llvm.mul %17, %105 : i64
    %107 = llvm.add %106, %14 : i64
    %108 = llvm.getelementptr %104[%107] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %109 = llvm.load %108 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%109, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %110 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %111 = llvm.mlir.constant(32 : index) : i64
    %112 = llvm.mul %13, %111 : i64
    %113 = llvm.add %112, %17 : i64
    %114 = llvm.getelementptr %110[%113] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %115 = llvm.load %114 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%115, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %116 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %117 = llvm.mlir.constant(32 : index) : i64
    %118 = llvm.mul %13, %117 : i64
    %119 = llvm.add %118, %16 : i64
    %120 = llvm.getelementptr %116[%119] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %121 = llvm.load %120 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%121, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %122 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %123 = llvm.mlir.constant(32 : index) : i64
    %124 = llvm.mul %13, %123 : i64
    %125 = llvm.add %124, %15 : i64
    %126 = llvm.getelementptr %122[%125] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %127 = llvm.load %126 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%127, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %128 = llvm.extractvalue %32[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %129 = llvm.mlir.constant(32 : index) : i64
    %130 = llvm.mul %13, %129 : i64
    %131 = llvm.add %130, %14 : i64
    %132 = llvm.getelementptr %128[%131] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %133 = llvm.load %132 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%133, %19) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%19) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %134 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %135 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %136 = llvm.mlir.constant(128 : index) : i64
    %137 = llvm.mul %17, %136 : i64
    %138 = llvm.add %137, %17 : i64
    %139 = llvm.getelementptr %135[%138] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %140 = llvm.load %139 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %141 = llvm.fadd %140, %134  : vector<8xf32>
    %142 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %143 = llvm.mlir.constant(128 : index) : i64
    %144 = llvm.mul %17, %143 : i64
    %145 = llvm.add %144, %17 : i64
    %146 = llvm.getelementptr %142[%145] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %141, %146 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %147 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %148 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %149 = llvm.mlir.constant(128 : index) : i64
    %150 = llvm.mul %17, %149 : i64
    %151 = llvm.add %150, %16 : i64
    %152 = llvm.getelementptr %148[%151] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %153 = llvm.load %152 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %154 = llvm.fadd %153, %147  : vector<8xf32>
    %155 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %156 = llvm.mlir.constant(128 : index) : i64
    %157 = llvm.mul %17, %156 : i64
    %158 = llvm.add %157, %16 : i64
    %159 = llvm.getelementptr %155[%158] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %154, %159 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %160 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %161 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %162 = llvm.mlir.constant(128 : index) : i64
    %163 = llvm.mul %17, %162 : i64
    %164 = llvm.add %163, %15 : i64
    %165 = llvm.getelementptr %161[%164] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %166 = llvm.load %165 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %167 = llvm.fadd %166, %160  : vector<8xf32>
    %168 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %169 = llvm.mlir.constant(128 : index) : i64
    %170 = llvm.mul %17, %169 : i64
    %171 = llvm.add %170, %15 : i64
    %172 = llvm.getelementptr %168[%171] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %167, %172 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %173 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %174 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %175 = llvm.mlir.constant(128 : index) : i64
    %176 = llvm.mul %17, %175 : i64
    %177 = llvm.add %176, %14 : i64
    %178 = llvm.getelementptr %174[%177] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %179 = llvm.load %178 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %180 = llvm.fadd %179, %173  : vector<8xf32>
    %181 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %182 = llvm.mlir.constant(128 : index) : i64
    %183 = llvm.mul %17, %182 : i64
    %184 = llvm.add %183, %14 : i64
    %185 = llvm.getelementptr %181[%184] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %180, %185 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %186 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %187 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %188 = llvm.mlir.constant(128 : index) : i64
    %189 = llvm.mul %17, %188 : i64
    %190 = llvm.add %189, %12 : i64
    %191 = llvm.getelementptr %187[%190] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %192 = llvm.load %191 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %193 = llvm.fadd %192, %186  : vector<8xf32>
    %194 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %195 = llvm.mlir.constant(128 : index) : i64
    %196 = llvm.mul %17, %195 : i64
    %197 = llvm.add %196, %12 : i64
    %198 = llvm.getelementptr %194[%197] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %193, %198 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %199 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %200 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %201 = llvm.mlir.constant(128 : index) : i64
    %202 = llvm.mul %17, %201 : i64
    %203 = llvm.add %202, %11 : i64
    %204 = llvm.getelementptr %200[%203] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %205 = llvm.load %204 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %206 = llvm.fadd %205, %199  : vector<8xf32>
    %207 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %208 = llvm.mlir.constant(128 : index) : i64
    %209 = llvm.mul %17, %208 : i64
    %210 = llvm.add %209, %11 : i64
    %211 = llvm.getelementptr %207[%210] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %206, %211 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %212 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %213 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %214 = llvm.mlir.constant(128 : index) : i64
    %215 = llvm.mul %17, %214 : i64
    %216 = llvm.add %215, %10 : i64
    %217 = llvm.getelementptr %213[%216] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %218 = llvm.load %217 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %219 = llvm.fadd %218, %212  : vector<8xf32>
    %220 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %221 = llvm.mlir.constant(128 : index) : i64
    %222 = llvm.mul %17, %221 : i64
    %223 = llvm.add %222, %10 : i64
    %224 = llvm.getelementptr %220[%223] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %219, %224 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %225 = "vcix.v.i"(%19) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %226 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %227 = llvm.mlir.constant(128 : index) : i64
    %228 = llvm.mul %17, %227 : i64
    %229 = llvm.add %228, %9 : i64
    %230 = llvm.getelementptr %226[%229] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %231 = llvm.load %230 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %232 = llvm.fadd %231, %225  : vector<8xf32>
    %233 = llvm.extractvalue %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %234 = llvm.mlir.constant(128 : index) : i64
    %235 = llvm.mul %17, %234 : i64
    %236 = llvm.add %235, %9 : i64
    %237 = llvm.getelementptr %233[%236] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %232, %237 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %238 = llvm.add %60, %12 : i64
    llvm.br ^bb5(%238 : i64)
  ^bb7:  // pred: ^bb5
    %239 = llvm.add %53, %0 : i64
    llvm.br ^bb3(%239 : i64)
  ^bb8:  // pred: ^bb3
    %240 = llvm.add %51, %1 : i64
    llvm.br ^bb1(%240 : i64)
  ^bb9:  // pred: ^bb1
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

