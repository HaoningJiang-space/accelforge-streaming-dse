module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<8 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<8 x array<32 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<32 x f32>>
  llvm.func @kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: !llvm.ptr, %arg6: !llvm.ptr, %arg7: i64, %arg8: i64, %arg9: i64, %arg10: !llvm.ptr, %arg11: !llvm.ptr, %arg12: i64, %arg13: i64, %arg14: i64) {
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
    %18 = llvm.mlir.constant(1024 : index) : i64
    %19 = llvm.mlir.constant(512 : index) : i64
    %20 = llvm.mlir.constant(32 : index) : i64
    %21 = llvm.mlir.constant(128 : index) : i64
    %22 = llvm.mlir.constant(16 : index) : i64
    %23 = llvm.mlir.constant(64 : index) : i64
    %24 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %25 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %26 = llvm.mlir.constant(0 : index) : i64
    %27 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %28 = llvm.mlir.constant(3735928559 : index) : i64
    %29 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %30 = llvm.mlir.constant(1 : index) : i64
    %31 = llvm.mlir.constant(16 : index) : i64
    %32 = llvm.mlir.constant(8 : index) : i64
    %33 = llvm.mlir.constant(1 : index) : i64
    %34 = llvm.mlir.constant(4295409668 : i64) : i64
    %35 = llvm.mlir.constant(281479272726560 : i64) : i64
    %36 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %37 = llvm.mlir.constant(8 : i64) : i64
    %38 = llvm.mlir.constant(4294967304 : i64) : i64
    %39 = llvm.mlir.constant(549755813889 : i64) : i64
    %40 = llvm.mlir.constant(281479272202272 : i64) : i64
    %41 = llvm.mlir.constant(32 : index) : i64
    %42 = llvm.mlir.constant(4294967312 : i64) : i64
    %43 = llvm.mlir.constant(137438953473 : i64) : i64
    %44 = llvm.mlir.constant(0 : i64) : i64
    %45 = llvm.mlir.constant(4295016452 : i64) : i64
    %46 = llvm.mlir.constant(281479272726536 : i64) : i64
    %47 = llvm.mlir.constant(8 : index) : i64
    %48 = llvm.mlir.constant(0 : index) : i64
    %49 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %50 = llvm.getelementptr %29[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<8 x f32>>
    %51 = llvm.inttoptr %28 : i64 to !llvm.ptr<1>
    %52 = llvm.insertvalue %51, %27[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.insertvalue %50, %52[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %54 = llvm.insertvalue %26, %53[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %55 = llvm.insertvalue %31, %54[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.insertvalue %47, %55[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %57 = llvm.insertvalue %47, %56[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.insertvalue %30, %57[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.getelementptr %25[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<8 x array<32 x f32>>
    %60 = llvm.inttoptr %28 : i64 to !llvm.ptr<1>
    %61 = llvm.insertvalue %60, %27[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.insertvalue %59, %61[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.insertvalue %26, %62[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.insertvalue %47, %63[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.insertvalue %41, %64[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %66 = llvm.insertvalue %41, %65[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %67 = llvm.insertvalue %30, %66[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.getelementptr %24[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<32 x f32>>
    %69 = llvm.inttoptr %28 : i64 to !llvm.ptr<1>
    %70 = llvm.insertvalue %69, %27[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.insertvalue %68, %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %72 = llvm.insertvalue %26, %71[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %73 = llvm.insertvalue %31, %72[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.insertvalue %41, %73[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.insertvalue %41, %74[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.insertvalue %30, %75[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%48 : i64)
  ^bb1(%77: i64):  // 2 preds: ^bb0, ^bb17
    %78 = llvm.icmp "slt" %77, %23 : i64
    llvm.cond_br %78, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%48 : i64)
  ^bb3(%79: i64):  // 2 preds: ^bb2, ^bb16
    %80 = llvm.icmp "slt" %79, %21 : i64
    llvm.cond_br %80, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    %81 = llvm.extractvalue %76[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %82 = llvm.mlir.constant(32 : index) : i64
    %83 = llvm.mul %48, %82 : i64
    %84 = llvm.add %83, %48 : i64
    %85 = llvm.getelementptr %81[%84] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %49, %85 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.br ^bb5(%48 : i64)
  ^bb5(%86: i64):  // 2 preds: ^bb4, ^bb15
    %87 = llvm.icmp "slt" %86, %20 : i64
    llvm.cond_br %87, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%48 : i64)
  ^bb7(%88: i64):  // 2 preds: ^bb6, ^bb14
    %89 = llvm.icmp "slt" %88, %33 : i64
    llvm.cond_br %89, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%48 : i64)
  ^bb9(%90: i64):  // 2 preds: ^bb8, ^bb13
    %91 = llvm.icmp "slt" %90, %33 : i64
    llvm.cond_br %91, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%48 : i64)
  ^bb11(%92: i64):  // 2 preds: ^bb10, ^bb12
    %93 = llvm.icmp "slt" %92, %33 : i64
    llvm.cond_br %93, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %94 = llvm.mul %88, %22 : i64
    %95 = llvm.mul %88, %19 : i64
    %96 = llvm.mul %90, %32 : i64
    %97 = llvm.add %95, %96 : i64
    %98 = llvm.mul %77, %20 : i64
    %99 = llvm.add %97, %98 : i64
    %100 = llvm.add %99, %86 : i64
    %101 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %102 = llvm.getelementptr %101[%100] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %103 = llvm.mul %48, %47 : i64
    %104 = llvm.add %103, %94 : i64
    %105 = llvm.getelementptr %50[%104] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %106 = llvm.ptrtoint %102 : !llvm.ptr to i64
    %107 = llvm.ptrtoint %105 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %46, %45 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %43 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %42 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %106, %107 : (i64, i64) -> ()
    %108 = llvm.mul %90, %32 : i64
    %109 = llvm.mul %90, %18 : i64
    %110 = llvm.mul %92, %20 : i64
    %111 = llvm.add %109, %110 : i64
    %112 = llvm.mul %86, %21 : i64
    %113 = llvm.add %111, %112 : i64
    %114 = llvm.add %113, %79 : i64
    %115 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %116 = llvm.getelementptr %115[%114] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %117 = llvm.mul %48, %41 : i64
    %118 = llvm.add %117, %108 : i64
    %119 = llvm.getelementptr %59[%118] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %120 = llvm.ptrtoint %116 : !llvm.ptr to i64
    %121 = llvm.ptrtoint %119 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %40, %45 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %39 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %38 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %120, %121 : (i64, i64) -> ()
    %122 = llvm.add %92, %33 : i64
    llvm.br ^bb11(%122 : i64)
  ^bb13:  // pred: ^bb11
    %123 = llvm.add %90, %33 : i64
    llvm.br ^bb9(%123 : i64)
  ^bb14:  // pred: ^bb9
    %124 = llvm.add %88, %33 : i64
    llvm.br ^bb7(%124 : i64)
  ^bb15:  // pred: ^bb7
    %125 = llvm.extractvalue %67[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %126 = llvm.mlir.constant(32 : index) : i64
    %127 = llvm.mul %48, %126 : i64
    %128 = llvm.add %127, %48 : i64
    %129 = llvm.getelementptr %125[%128] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %130 = llvm.load %129 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%130, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%36, %37) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %131 = llvm.extractvalue %58[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %132 = llvm.mlir.constant(8 : index) : i64
    %133 = llvm.mul %48, %132 : i64
    %134 = llvm.add %133, %48 : i64
    %135 = llvm.getelementptr %131[%134] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %136 = llvm.load %135 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%136, %37) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %137 = llvm.extractvalue %58[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %138 = llvm.mlir.constant(8 : index) : i64
    %139 = llvm.mul %33, %138 : i64
    %140 = llvm.add %139, %48 : i64
    %141 = llvm.getelementptr %137[%140] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %142 = llvm.load %141 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%142, %37) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%37) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %143 = "vcix.v.i"(%37) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %144 = llvm.extractvalue %76[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %145 = llvm.mlir.constant(32 : index) : i64
    %146 = llvm.mul %48, %145 : i64
    %147 = llvm.add %146, %48 : i64
    %148 = llvm.getelementptr %144[%147] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %149 = llvm.load %148 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %150 = llvm.fadd %149, %143  : vector<8xf32>
    %151 = llvm.extractvalue %76[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %152 = llvm.mlir.constant(32 : index) : i64
    %153 = llvm.mul %48, %152 : i64
    %154 = llvm.add %153, %48 : i64
    %155 = llvm.getelementptr %151[%154] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %150, %155 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %156 = "vcix.v.i"(%37) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %157 = llvm.extractvalue %76[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %158 = llvm.mlir.constant(32 : index) : i64
    %159 = llvm.mul %48, %158 : i64
    %160 = llvm.add %159, %32 : i64
    %161 = llvm.getelementptr %157[%160] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %162 = llvm.load %161 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %163 = llvm.fadd %162, %156  : vector<8xf32>
    %164 = llvm.extractvalue %76[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %165 = llvm.mlir.constant(32 : index) : i64
    %166 = llvm.mul %48, %165 : i64
    %167 = llvm.add %166, %32 : i64
    %168 = llvm.getelementptr %164[%167] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %163, %168 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %169 = llvm.add %86, %32 : i64
    llvm.br ^bb5(%169 : i64)
  ^bb16:  // pred: ^bb5
    %170 = llvm.mul %77, %21 : i64
    %171 = llvm.add %170, %79 : i64
    %172 = llvm.mul %48, %41 : i64
    %173 = llvm.add %172, %48 : i64
    %174 = llvm.getelementptr %68[%173] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %175 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %176 = llvm.getelementptr %175[%171] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %177 = llvm.ptrtoint %176 : !llvm.ptr to i64
    %178 = llvm.ptrtoint %174 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %35, %34 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %39 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %42 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 3, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %177, %178 : (i64, i64) -> ()
    %179 = llvm.add %79, %20 : i64
    llvm.br ^bb3(%179 : i64)
  ^bb17:  // pred: ^bb3
    %180 = llvm.add %77, %22 : i64
    llvm.br ^bb1(%180 : i64)
  ^bb18:  // pred: ^bb1
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

