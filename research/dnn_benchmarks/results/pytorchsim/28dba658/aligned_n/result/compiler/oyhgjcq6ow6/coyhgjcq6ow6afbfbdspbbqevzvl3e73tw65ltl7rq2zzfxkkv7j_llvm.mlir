module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<16 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<256 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<256 x f32>>
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
    %18 = llvm.mlir.constant(128 : index) : i64
    %19 = llvm.mlir.constant(4096 : index) : i64
    %20 = llvm.mlir.constant(2 : index) : i64
    %21 = llvm.mlir.constant(1 : index) : i64
    %22 = llvm.mlir.constant(256 : index) : i64
    %23 = llvm.mlir.constant(16 : index) : i64
    %24 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %25 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %26 = llvm.mlir.constant(0 : index) : i64
    %27 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %28 = llvm.mlir.constant(3735928559 : index) : i64
    %29 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %30 = llvm.mlir.constant(1 : index) : i64
    %31 = llvm.mlir.constant(8 : index) : i64
    %32 = llvm.mlir.constant(4295409668 : i64) : i64
    %33 = llvm.mlir.constant(281479272726784 : i64) : i64
    %34 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %35 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %36 = llvm.mlir.constant(8 : i64) : i64
    %37 = llvm.mlir.constant(1099511627777 : i64) : i64
    %38 = llvm.mlir.constant(281479272726656 : i64) : i64
    %39 = llvm.mlir.constant(256 : index) : i64
    %40 = llvm.mlir.constant(4294967312 : i64) : i64
    %41 = llvm.mlir.constant(68719476737 : i64) : i64
    %42 = llvm.mlir.constant(0 : i64) : i64
    %43 = llvm.mlir.constant(4295016452 : i64) : i64
    %44 = llvm.mlir.constant(281479272726544 : i64) : i64
    %45 = llvm.mlir.constant(16 : index) : i64
    %46 = llvm.mlir.constant(0 : index) : i64
    %47 = llvm.mlir.constant(dense<0.000000e+00> : vector<32xf32>) : vector<32xf32>
    %48 = llvm.getelementptr %29[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<16 x f32>>
    %49 = llvm.inttoptr %28 : i64 to !llvm.ptr<1>
    %50 = llvm.insertvalue %49, %27[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %51 = llvm.insertvalue %48, %50[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %52 = llvm.insertvalue %26, %51[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.insertvalue %45, %52[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %54 = llvm.insertvalue %45, %53[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %55 = llvm.insertvalue %45, %54[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.insertvalue %30, %55[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %57 = llvm.getelementptr %25[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<256 x f32>>
    %58 = llvm.inttoptr %28 : i64 to !llvm.ptr<1>
    %59 = llvm.insertvalue %58, %27[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %60 = llvm.insertvalue %57, %59[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.insertvalue %26, %60[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.insertvalue %45, %61[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.insertvalue %39, %62[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.insertvalue %39, %63[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.insertvalue %30, %64[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %66 = llvm.getelementptr %24[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<256 x f32>>
    %67 = llvm.inttoptr %28 : i64 to !llvm.ptr<1>
    %68 = llvm.insertvalue %67, %27[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.insertvalue %66, %68[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.insertvalue %26, %69[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.insertvalue %45, %70[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %72 = llvm.insertvalue %39, %71[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %73 = llvm.insertvalue %39, %72[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.insertvalue %30, %73[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%46 : i64)
  ^bb1(%75: i64):  // 2 preds: ^bb0, ^bb20
    %76 = llvm.icmp "slt" %75, %23 : i64
    llvm.cond_br %76, ^bb2, ^bb21
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%46 : i64)
  ^bb3(%77: i64):  // 2 preds: ^bb2, ^bb19
    %78 = llvm.icmp "slt" %77, %22 : i64
    llvm.cond_br %78, ^bb4, ^bb20
  ^bb4:  // pred: ^bb3
    %79 = llvm.extractvalue %74[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %80 = llvm.mlir.constant(256 : index) : i64
    %81 = llvm.mul %46, %80 : i64
    %82 = llvm.add %81, %46 : i64
    %83 = llvm.getelementptr %79[%82] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %47, %83 {alignment = 4 : i64} : vector<32xf32>, !llvm.ptr<1>
    llvm.br ^bb5(%46 : i64)
  ^bb5(%84: i64):  // 2 preds: ^bb4, ^bb18
    %85 = llvm.icmp "slt" %84, %23 : i64
    llvm.cond_br %85, ^bb6, ^bb19
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%46 : i64)
  ^bb7(%86: i64):  // 2 preds: ^bb6, ^bb14
    %87 = llvm.icmp "slt" %86, %21 : i64
    llvm.cond_br %87, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%46 : i64)
  ^bb9(%88: i64):  // 2 preds: ^bb8, ^bb13
    %89 = llvm.icmp "slt" %88, %21 : i64
    llvm.cond_br %89, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%46 : i64)
  ^bb11(%90: i64):  // 2 preds: ^bb10, ^bb12
    %91 = llvm.icmp "slt" %90, %20 : i64
    llvm.cond_br %91, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %92 = llvm.mul %86, %23 : i64
    %93 = llvm.mul %86, %22 : i64
    %94 = llvm.mul %88, %23 : i64
    %95 = llvm.add %93, %94 : i64
    %96 = llvm.mul %75, %23 : i64
    %97 = llvm.add %95, %96 : i64
    %98 = llvm.add %97, %84 : i64
    %99 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %100 = llvm.getelementptr %99[%98] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %101 = llvm.mul %46, %45 : i64
    %102 = llvm.add %101, %92 : i64
    %103 = llvm.getelementptr %48[%102] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %104 = llvm.ptrtoint %100 : !llvm.ptr to i64
    %105 = llvm.ptrtoint %103 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %43 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %42, %41 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %42, %40 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %104, %105 : (i64, i64) -> ()
    %106 = llvm.mul %88, %23 : i64
    %107 = llvm.mul %90, %23 : i64
    %108 = llvm.add %106, %107 : i64
    %109 = llvm.mul %88, %19 : i64
    %110 = llvm.mul %90, %18 : i64
    %111 = llvm.add %109, %110 : i64
    %112 = llvm.mul %84, %22 : i64
    %113 = llvm.add %111, %112 : i64
    %114 = llvm.add %113, %77 : i64
    %115 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %116 = llvm.getelementptr %115[%114] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %117 = llvm.mul %46, %39 : i64
    %118 = llvm.add %117, %108 : i64
    %119 = llvm.getelementptr %57[%118] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %120 = llvm.ptrtoint %116 : !llvm.ptr to i64
    %121 = llvm.ptrtoint %119 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %38, %43 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %42, %37 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %42, %40 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %120, %121 : (i64, i64) -> ()
    %122 = llvm.add %90, %21 : i64
    llvm.br ^bb11(%122 : i64)
  ^bb13:  // pred: ^bb11
    %123 = llvm.add %88, %21 : i64
    llvm.br ^bb9(%123 : i64)
  ^bb14:  // pred: ^bb9
    %124 = llvm.add %86, %21 : i64
    llvm.br ^bb7(%124 : i64)
  ^bb15:  // pred: ^bb7
    llvm.br ^bb16(%46 : i64)
  ^bb16(%125: i64):  // 2 preds: ^bb15, ^bb17
    %126 = llvm.icmp "slt" %125, %20 : i64
    llvm.cond_br %126, ^bb17, ^bb18
  ^bb17:  // pred: ^bb16
    %127 = llvm.mul %125, %23 : i64
    %128 = llvm.mlir.constant(1 : index) : i64
    %129 = llvm.mlir.constant(256 : index) : i64
    %130 = llvm.sub %129, %127 : i64
    %131 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %132 = llvm.trunc %130 : i64 to i32
    %133 = llvm.mlir.undef : vector<8xi32>
    %134 = llvm.mlir.constant(0 : i32) : i32
    %135 = llvm.insertelement %132, %133[%134 : i32] : vector<8xi32>
    %136 = llvm.shufflevector %135, %133 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %137 = llvm.icmp "sgt" %136, %131 : vector<8xi32>
    %138 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %139 = llvm.extractvalue %65[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %140 = llvm.mlir.constant(256 : index) : i64
    %141 = llvm.mul %46, %140 : i64
    %142 = llvm.add %141, %127 : i64
    %143 = llvm.getelementptr %139[%142] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %144 = llvm.intr.masked.load %143, %137, %138 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    "vcix.iv"(%144, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %145 = llvm.mul %125, %23 : i64
    %146 = llvm.add %145, %31 : i64
    %147 = llvm.mlir.constant(1 : index) : i64
    %148 = llvm.mlir.constant(256 : index) : i64
    %149 = llvm.sub %148, %146 : i64
    %150 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %151 = llvm.trunc %149 : i64 to i32
    %152 = llvm.mlir.undef : vector<8xi32>
    %153 = llvm.mlir.constant(0 : i32) : i32
    %154 = llvm.insertelement %151, %152[%153 : i32] : vector<8xi32>
    %155 = llvm.shufflevector %154, %152 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %156 = llvm.icmp "sgt" %155, %150 : vector<8xi32>
    %157 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %158 = llvm.extractvalue %65[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %159 = llvm.mlir.constant(256 : index) : i64
    %160 = llvm.mul %46, %159 : i64
    %161 = llvm.add %160, %146 : i64
    %162 = llvm.getelementptr %158[%161] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %163 = llvm.intr.masked.load %162, %156, %157 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    "vcix.iv"(%163, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%35, %36) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %164 = llvm.extractvalue %56[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %165 = llvm.mlir.constant(16 : index) : i64
    %166 = llvm.mul %46, %165 : i64
    %167 = llvm.add %166, %46 : i64
    %168 = llvm.getelementptr %164[%167] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %169 = llvm.load %168 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%169, %36) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %170 = llvm.extractvalue %56[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %171 = llvm.mlir.constant(16 : index) : i64
    %172 = llvm.mul %46, %171 : i64
    %173 = llvm.add %172, %31 : i64
    %174 = llvm.getelementptr %170[%173] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %175 = llvm.load %174 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%175, %36) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%36) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %176 = "vcix.v.i"(%36) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %177 = llvm.mul %125, %23 : i64
    %178 = llvm.mlir.constant(1 : index) : i64
    %179 = llvm.mlir.constant(256 : index) : i64
    %180 = llvm.sub %179, %177 : i64
    %181 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %182 = llvm.trunc %180 : i64 to i32
    %183 = llvm.mlir.undef : vector<8xi32>
    %184 = llvm.mlir.constant(0 : i32) : i32
    %185 = llvm.insertelement %182, %183[%184 : i32] : vector<8xi32>
    %186 = llvm.shufflevector %185, %183 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %187 = llvm.icmp "sgt" %186, %181 : vector<8xi32>
    %188 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %189 = llvm.extractvalue %74[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %190 = llvm.mlir.constant(256 : index) : i64
    %191 = llvm.mul %46, %190 : i64
    %192 = llvm.add %191, %177 : i64
    %193 = llvm.getelementptr %189[%192] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %194 = llvm.intr.masked.load %193, %187, %188 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    %195 = llvm.fadd %194, %176  : vector<8xf32>
    %196 = llvm.mlir.constant(1 : index) : i64
    %197 = llvm.mlir.constant(256 : index) : i64
    %198 = llvm.sub %197, %177 : i64
    %199 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %200 = llvm.trunc %198 : i64 to i32
    %201 = llvm.mlir.undef : vector<8xi32>
    %202 = llvm.mlir.constant(0 : i32) : i32
    %203 = llvm.insertelement %200, %201[%202 : i32] : vector<8xi32>
    %204 = llvm.shufflevector %203, %201 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %205 = llvm.icmp "sgt" %204, %199 : vector<8xi32>
    %206 = llvm.extractvalue %74[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %207 = llvm.mlir.constant(256 : index) : i64
    %208 = llvm.mul %46, %207 : i64
    %209 = llvm.add %208, %177 : i64
    %210 = llvm.getelementptr %206[%209] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.intr.masked.store %195, %210, %205 {alignment = 4 : i32} : vector<8xf32>, vector<8xi1> into !llvm.ptr<1>
    %211 = "vcix.v.i"(%36) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %212 = llvm.mul %125, %23 : i64
    %213 = llvm.add %212, %31 : i64
    %214 = llvm.mlir.constant(1 : index) : i64
    %215 = llvm.mlir.constant(256 : index) : i64
    %216 = llvm.sub %215, %213 : i64
    %217 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %218 = llvm.trunc %216 : i64 to i32
    %219 = llvm.mlir.undef : vector<8xi32>
    %220 = llvm.mlir.constant(0 : i32) : i32
    %221 = llvm.insertelement %218, %219[%220 : i32] : vector<8xi32>
    %222 = llvm.shufflevector %221, %219 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %223 = llvm.icmp "sgt" %222, %217 : vector<8xi32>
    %224 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %225 = llvm.extractvalue %74[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %226 = llvm.mlir.constant(256 : index) : i64
    %227 = llvm.mul %46, %226 : i64
    %228 = llvm.add %227, %213 : i64
    %229 = llvm.getelementptr %225[%228] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %230 = llvm.intr.masked.load %229, %223, %224 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    %231 = llvm.fadd %230, %211  : vector<8xf32>
    %232 = llvm.mlir.constant(1 : index) : i64
    %233 = llvm.mlir.constant(256 : index) : i64
    %234 = llvm.sub %233, %213 : i64
    %235 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %236 = llvm.trunc %234 : i64 to i32
    %237 = llvm.mlir.undef : vector<8xi32>
    %238 = llvm.mlir.constant(0 : i32) : i32
    %239 = llvm.insertelement %236, %237[%238 : i32] : vector<8xi32>
    %240 = llvm.shufflevector %239, %237 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %241 = llvm.icmp "sgt" %240, %235 : vector<8xi32>
    %242 = llvm.extractvalue %74[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %243 = llvm.mlir.constant(256 : index) : i64
    %244 = llvm.mul %46, %243 : i64
    %245 = llvm.add %244, %213 : i64
    %246 = llvm.getelementptr %242[%245] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.intr.masked.store %231, %246, %241 {alignment = 4 : i32} : vector<8xf32>, vector<8xi1> into !llvm.ptr<1>
    %247 = llvm.add %125, %21 : i64
    llvm.br ^bb16(%247 : i64)
  ^bb18:  // pred: ^bb16
    %248 = llvm.add %84, %23 : i64
    llvm.br ^bb5(%248 : i64)
  ^bb19:  // pred: ^bb5
    %249 = llvm.mul %75, %22 : i64
    %250 = llvm.add %249, %77 : i64
    %251 = llvm.mul %46, %39 : i64
    %252 = llvm.add %251, %46 : i64
    %253 = llvm.getelementptr %66[%252] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %254 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %255 = llvm.getelementptr %254[%250] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %256 = llvm.ptrtoint %255 : !llvm.ptr to i64
    %257 = llvm.ptrtoint %253 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %33, %32 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %42, %37 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %42, %40 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 3, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %256, %257 : (i64, i64) -> ()
    %258 = llvm.add %77, %22 : i64
    llvm.br ^bb3(%258 : i64)
  ^bb20:  // pred: ^bb3
    %259 = llvm.add %75, %23 : i64
    llvm.br ^bb1(%259 : i64)
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

