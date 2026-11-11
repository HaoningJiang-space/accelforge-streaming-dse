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
    %19 = llvm.mlir.constant(256 : index) : i64
    %20 = llvm.mlir.constant(1 : index) : i64
    %21 = llvm.mlir.constant(2 : index) : i64
    %22 = llvm.mlir.constant(8 : index) : i64
    %23 = llvm.mlir.constant(32 : index) : i64
    %24 = llvm.mlir.constant(128 : index) : i64
    %25 = llvm.mlir.constant(16 : index) : i64
    %26 = llvm.mlir.constant(64 : index) : i64
    %27 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %28 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %29 = llvm.mlir.constant(0 : index) : i64
    %30 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %31 = llvm.mlir.constant(3735928559 : index) : i64
    %32 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %33 = llvm.mlir.constant(1 : index) : i64
    %34 = llvm.mlir.constant(16 : index) : i64
    %35 = llvm.mlir.constant(4295409668 : i64) : i64
    %36 = llvm.mlir.constant(281479272726560 : i64) : i64
    %37 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %38 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %39 = llvm.mlir.constant(8 : i64) : i64
    %40 = llvm.mlir.constant(4294967304 : i64) : i64
    %41 = llvm.mlir.constant(549755813889 : i64) : i64
    %42 = llvm.mlir.constant(281479272202272 : i64) : i64
    %43 = llvm.mlir.constant(32 : index) : i64
    %44 = llvm.mlir.constant(4294967312 : i64) : i64
    %45 = llvm.mlir.constant(137438953473 : i64) : i64
    %46 = llvm.mlir.constant(0 : i64) : i64
    %47 = llvm.mlir.constant(4295016452 : i64) : i64
    %48 = llvm.mlir.constant(281479272202248 : i64) : i64
    %49 = llvm.mlir.constant(8 : index) : i64
    %50 = llvm.mlir.constant(0 : index) : i64
    %51 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %52 = llvm.getelementptr %32[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<8 x f32>>
    %53 = llvm.inttoptr %31 : i64 to !llvm.ptr<1>
    %54 = llvm.insertvalue %53, %30[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %55 = llvm.insertvalue %52, %54[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.insertvalue %29, %55[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %57 = llvm.insertvalue %34, %56[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.insertvalue %49, %57[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.insertvalue %49, %58[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %60 = llvm.insertvalue %33, %59[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.getelementptr %28[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<8 x array<32 x f32>>
    %62 = llvm.inttoptr %31 : i64 to !llvm.ptr<1>
    %63 = llvm.insertvalue %62, %30[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.insertvalue %61, %63[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.insertvalue %29, %64[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %66 = llvm.insertvalue %49, %65[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %67 = llvm.insertvalue %43, %66[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.insertvalue %43, %67[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.insertvalue %33, %68[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.getelementptr %27[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<32 x f32>>
    %71 = llvm.inttoptr %31 : i64 to !llvm.ptr<1>
    %72 = llvm.insertvalue %71, %30[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %73 = llvm.insertvalue %70, %72[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.insertvalue %29, %73[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.insertvalue %34, %74[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.insertvalue %43, %75[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.insertvalue %43, %76[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %78 = llvm.insertvalue %33, %77[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%50 : i64)
  ^bb1(%79: i64):  // 2 preds: ^bb0, ^bb20
    %80 = llvm.icmp "slt" %79, %26 : i64
    llvm.cond_br %80, ^bb2, ^bb21
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%50 : i64)
  ^bb3(%81: i64):  // 2 preds: ^bb2, ^bb19
    %82 = llvm.icmp "slt" %81, %24 : i64
    llvm.cond_br %82, ^bb4, ^bb20
  ^bb4:  // pred: ^bb3
    %83 = llvm.extractvalue %78[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %84 = llvm.mlir.constant(32 : index) : i64
    %85 = llvm.mul %50, %84 : i64
    %86 = llvm.add %85, %50 : i64
    %87 = llvm.getelementptr %83[%86] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %51, %87 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.br ^bb5(%50 : i64)
  ^bb5(%88: i64):  // 2 preds: ^bb4, ^bb18
    %89 = llvm.icmp "slt" %88, %23 : i64
    llvm.cond_br %89, ^bb6, ^bb19
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%50 : i64)
  ^bb7(%90: i64):  // 2 preds: ^bb6, ^bb14
    %91 = llvm.icmp "slt" %90, %21 : i64
    llvm.cond_br %91, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%50 : i64)
  ^bb9(%92: i64):  // 2 preds: ^bb8, ^bb13
    %93 = llvm.icmp "slt" %92, %20 : i64
    llvm.cond_br %93, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%50 : i64)
  ^bb11(%94: i64):  // 2 preds: ^bb10, ^bb12
    %95 = llvm.icmp "slt" %94, %20 : i64
    llvm.cond_br %95, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %96 = llvm.mul %90, %22 : i64
    %97 = llvm.mul %90, %19 : i64
    %98 = llvm.mul %92, %22 : i64
    %99 = llvm.add %97, %98 : i64
    %100 = llvm.mul %79, %23 : i64
    %101 = llvm.add %99, %100 : i64
    %102 = llvm.add %101, %88 : i64
    %103 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %104 = llvm.getelementptr %103[%102] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %105 = llvm.mul %50, %49 : i64
    %106 = llvm.add %105, %96 : i64
    %107 = llvm.getelementptr %52[%106] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %108 = llvm.ptrtoint %104 : !llvm.ptr to i64
    %109 = llvm.ptrtoint %107 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %48, %47 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %46, %45 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %46, %44 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %108, %109 : (i64, i64) -> ()
    %110 = llvm.mul %92, %22 : i64
    %111 = llvm.mul %92, %18 : i64
    %112 = llvm.mul %94, %23 : i64
    %113 = llvm.add %111, %112 : i64
    %114 = llvm.mul %88, %24 : i64
    %115 = llvm.add %113, %114 : i64
    %116 = llvm.add %115, %81 : i64
    %117 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %118 = llvm.getelementptr %117[%116] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %119 = llvm.mul %50, %43 : i64
    %120 = llvm.add %119, %110 : i64
    %121 = llvm.getelementptr %61[%120] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %122 = llvm.ptrtoint %118 : !llvm.ptr to i64
    %123 = llvm.ptrtoint %121 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %42, %47 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %46, %41 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %46, %40 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %122, %123 : (i64, i64) -> ()
    %124 = llvm.add %94, %20 : i64
    llvm.br ^bb11(%124 : i64)
  ^bb13:  // pred: ^bb11
    %125 = llvm.add %92, %20 : i64
    llvm.br ^bb9(%125 : i64)
  ^bb14:  // pred: ^bb9
    %126 = llvm.add %90, %20 : i64
    llvm.br ^bb7(%126 : i64)
  ^bb15:  // pred: ^bb7
    %127 = llvm.extractvalue %69[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %128 = llvm.mlir.constant(32 : index) : i64
    %129 = llvm.mul %50, %128 : i64
    %130 = llvm.add %129, %50 : i64
    %131 = llvm.getelementptr %127[%130] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %132 = llvm.load %131 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%132, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%38, %39) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    llvm.br ^bb16(%50 : i64)
  ^bb16(%133: i64):  // 2 preds: ^bb15, ^bb17
    %134 = llvm.icmp "slt" %133, %21 : i64
    llvm.cond_br %134, ^bb17, ^bb18
  ^bb17:  // pred: ^bb16
    %135 = llvm.extractvalue %60[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %136 = llvm.mlir.constant(8 : index) : i64
    %137 = llvm.mul %133, %136 : i64
    %138 = llvm.add %137, %50 : i64
    %139 = llvm.getelementptr %135[%138] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %140 = llvm.load %139 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%140, %39) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%39) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %141 = "vcix.v.i"(%39) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %142 = llvm.mul %133, %22 : i64
    %143 = llvm.mlir.constant(1 : index) : i64
    %144 = llvm.mlir.constant(32 : index) : i64
    %145 = llvm.sub %144, %142 : i64
    %146 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %147 = llvm.trunc %145 : i64 to i32
    %148 = llvm.mlir.undef : vector<8xi32>
    %149 = llvm.mlir.constant(0 : i32) : i32
    %150 = llvm.insertelement %147, %148[%149 : i32] : vector<8xi32>
    %151 = llvm.shufflevector %150, %148 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %152 = llvm.icmp "sgt" %151, %146 : vector<8xi32>
    %153 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %154 = llvm.extractvalue %78[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %155 = llvm.mlir.constant(32 : index) : i64
    %156 = llvm.mul %50, %155 : i64
    %157 = llvm.add %156, %142 : i64
    %158 = llvm.getelementptr %154[%157] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %159 = llvm.intr.masked.load %158, %152, %153 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    %160 = llvm.fadd %159, %141  : vector<8xf32>
    %161 = llvm.mlir.constant(1 : index) : i64
    %162 = llvm.mlir.constant(32 : index) : i64
    %163 = llvm.sub %162, %142 : i64
    %164 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %165 = llvm.trunc %163 : i64 to i32
    %166 = llvm.mlir.undef : vector<8xi32>
    %167 = llvm.mlir.constant(0 : i32) : i32
    %168 = llvm.insertelement %165, %166[%167 : i32] : vector<8xi32>
    %169 = llvm.shufflevector %168, %166 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %170 = llvm.icmp "sgt" %169, %164 : vector<8xi32>
    %171 = llvm.extractvalue %78[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %172 = llvm.mlir.constant(32 : index) : i64
    %173 = llvm.mul %50, %172 : i64
    %174 = llvm.add %173, %142 : i64
    %175 = llvm.getelementptr %171[%174] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.intr.masked.store %160, %175, %170 {alignment = 4 : i32} : vector<8xf32>, vector<8xi1> into !llvm.ptr<1>
    %176 = llvm.add %133, %20 : i64
    llvm.br ^bb16(%176 : i64)
  ^bb18:  // pred: ^bb16
    %177 = llvm.add %88, %22 : i64
    llvm.br ^bb5(%177 : i64)
  ^bb19:  // pred: ^bb5
    %178 = llvm.mul %79, %24 : i64
    %179 = llvm.add %178, %81 : i64
    %180 = llvm.mul %50, %43 : i64
    %181 = llvm.add %180, %50 : i64
    %182 = llvm.getelementptr %70[%181] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %183 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %184 = llvm.getelementptr %183[%179] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %185 = llvm.ptrtoint %184 : !llvm.ptr to i64
    %186 = llvm.ptrtoint %182 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %36, %35 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %46, %41 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %46, %44 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 3, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %185, %186 : (i64, i64) -> ()
    %187 = llvm.add %81, %23 : i64
    llvm.br ^bb3(%187 : i64)
  ^bb20:  // pred: ^bb3
    %188 = llvm.add %79, %25 : i64
    llvm.br ^bb1(%188 : i64)
  ^bb21:  // pred: ^bb1
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

