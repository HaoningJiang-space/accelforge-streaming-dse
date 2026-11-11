module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<64 x array<32 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<32 x array<128 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<64 x array<128 x f32>>
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
    %18 = llvm.mlir.constant(4096 : index) : i64
    %19 = llvm.mlir.constant(2048 : index) : i64
    %20 = llvm.mlir.constant(128 : index) : i64
    %21 = llvm.mlir.constant(64 : index) : i64
    %22 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %23 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %24 = llvm.mlir.constant(0 : index) : i64
    %25 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %26 = llvm.mlir.constant(3735928559 : index) : i64
    %27 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %28 = llvm.mlir.constant(1 : index) : i64
    %29 = llvm.mlir.constant(64 : index) : i64
    %30 = llvm.mlir.constant(56 : index) : i64
    %31 = llvm.mlir.constant(48 : index) : i64
    %32 = llvm.mlir.constant(40 : index) : i64
    %33 = llvm.mlir.constant(32 : index) : i64
    %34 = llvm.mlir.constant(1 : index) : i64
    %35 = llvm.mlir.constant(24 : index) : i64
    %36 = llvm.mlir.constant(16 : index) : i64
    %37 = llvm.mlir.constant(8 : index) : i64
    %38 = llvm.mlir.constant(4295409668 : i64) : i64
    %39 = llvm.mlir.constant(281479275872384 : i64) : i64
    %40 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %41 = llvm.mlir.constant(8 : i64) : i64
    %42 = llvm.mlir.constant(4294967328 : i64) : i64
    %43 = llvm.mlir.constant(549755813889 : i64) : i64
    %44 = llvm.mlir.constant(281479273775232 : i64) : i64
    %45 = llvm.mlir.constant(128 : index) : i64
    %46 = llvm.mlir.constant(4294967360 : i64) : i64
    %47 = llvm.mlir.constant(137438953473 : i64) : i64
    %48 = llvm.mlir.constant(0 : i64) : i64
    %49 = llvm.mlir.constant(4295016452 : i64) : i64
    %50 = llvm.mlir.constant(281479275872288 : i64) : i64
    %51 = llvm.mlir.constant(32 : index) : i64
    %52 = llvm.mlir.constant(0 : index) : i64
    %53 = llvm.mlir.constant(dense<0.000000e+00> : vector<64xf32>) : vector<64xf32>
    %54 = llvm.getelementptr %27[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<64 x array<32 x f32>>
    %55 = llvm.inttoptr %26 : i64 to !llvm.ptr<1>
    %56 = llvm.insertvalue %55, %25[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %57 = llvm.insertvalue %54, %56[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.insertvalue %24, %57[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.insertvalue %29, %58[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %60 = llvm.insertvalue %51, %59[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.insertvalue %51, %60[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.insertvalue %28, %61[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.getelementptr %23[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<32 x array<128 x f32>>
    %64 = llvm.inttoptr %26 : i64 to !llvm.ptr<1>
    %65 = llvm.insertvalue %64, %25[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %66 = llvm.insertvalue %63, %65[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %67 = llvm.insertvalue %24, %66[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.insertvalue %51, %67[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.insertvalue %45, %68[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.insertvalue %45, %69[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.insertvalue %28, %70[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %72 = llvm.getelementptr %22[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<64 x array<128 x f32>>
    %73 = llvm.inttoptr %26 : i64 to !llvm.ptr<1>
    %74 = llvm.insertvalue %73, %25[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.insertvalue %72, %74[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.insertvalue %24, %75[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.insertvalue %29, %76[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %78 = llvm.insertvalue %45, %77[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %79 = llvm.insertvalue %45, %78[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %80 = llvm.insertvalue %28, %79[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%52 : i64)
  ^bb1(%81: i64):  // 2 preds: ^bb0, ^bb17
    %82 = llvm.icmp "slt" %81, %21 : i64
    llvm.cond_br %82, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%52 : i64)
  ^bb3(%83: i64):  // 2 preds: ^bb2, ^bb16
    %84 = llvm.icmp "slt" %83, %20 : i64
    llvm.cond_br %84, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    %85 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %86 = llvm.mlir.constant(128 : index) : i64
    %87 = llvm.mul %52, %86 : i64
    %88 = llvm.add %87, %52 : i64
    %89 = llvm.getelementptr %85[%88] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %53, %89 {alignment = 4 : i64} : vector<64xf32>, !llvm.ptr<1>
    llvm.br ^bb5(%52 : i64)
  ^bb5(%90: i64):  // 2 preds: ^bb4, ^bb15
    %91 = llvm.icmp "slt" %90, %33 : i64
    llvm.cond_br %91, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%52 : i64)
  ^bb7(%92: i64):  // 2 preds: ^bb6, ^bb14
    %93 = llvm.icmp "slt" %92, %34 : i64
    llvm.cond_br %93, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%52 : i64)
  ^bb9(%94: i64):  // 2 preds: ^bb8, ^bb13
    %95 = llvm.icmp "slt" %94, %34 : i64
    llvm.cond_br %95, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%52 : i64)
  ^bb11(%96: i64):  // 2 preds: ^bb10, ^bb12
    %97 = llvm.icmp "slt" %96, %34 : i64
    llvm.cond_br %97, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %98 = llvm.mul %92, %21 : i64
    %99 = llvm.mul %92, %19 : i64
    %100 = llvm.mul %94, %33 : i64
    %101 = llvm.add %99, %100 : i64
    %102 = llvm.mul %81, %33 : i64
    %103 = llvm.add %101, %102 : i64
    %104 = llvm.add %103, %90 : i64
    %105 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %106 = llvm.getelementptr %105[%104] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %107 = llvm.mul %52, %51 : i64
    %108 = llvm.add %107, %98 : i64
    %109 = llvm.getelementptr %54[%108] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %110 = llvm.ptrtoint %106 : !llvm.ptr to i64
    %111 = llvm.ptrtoint %109 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %50, %49 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %48, %47 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %48, %46 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %110, %111 : (i64, i64) -> ()
    %112 = llvm.mul %94, %33 : i64
    %113 = llvm.mul %96, %33 : i64
    %114 = llvm.add %112, %113 : i64
    %115 = llvm.mul %94, %18 : i64
    %116 = llvm.mul %96, %20 : i64
    %117 = llvm.add %115, %116 : i64
    %118 = llvm.mul %90, %20 : i64
    %119 = llvm.add %117, %118 : i64
    %120 = llvm.add %119, %83 : i64
    %121 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %122 = llvm.getelementptr %121[%120] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %123 = llvm.mul %52, %45 : i64
    %124 = llvm.add %123, %114 : i64
    %125 = llvm.getelementptr %63[%124] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %126 = llvm.ptrtoint %122 : !llvm.ptr to i64
    %127 = llvm.ptrtoint %125 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %44, %49 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %48, %43 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %48, %42 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %126, %127 : (i64, i64) -> ()
    %128 = llvm.add %96, %34 : i64
    llvm.br ^bb11(%128 : i64)
  ^bb13:  // pred: ^bb11
    %129 = llvm.add %94, %34 : i64
    llvm.br ^bb9(%129 : i64)
  ^bb14:  // pred: ^bb9
    %130 = llvm.add %92, %34 : i64
    llvm.br ^bb7(%130 : i64)
  ^bb15:  // pred: ^bb7
    %131 = llvm.extractvalue %71[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %132 = llvm.mlir.constant(128 : index) : i64
    %133 = llvm.mul %52, %132 : i64
    %134 = llvm.add %133, %52 : i64
    %135 = llvm.getelementptr %131[%134] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %136 = llvm.load %135 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%136, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %137 = llvm.extractvalue %71[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %138 = llvm.mlir.constant(128 : index) : i64
    %139 = llvm.mul %52, %138 : i64
    %140 = llvm.add %139, %37 : i64
    %141 = llvm.getelementptr %137[%140] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %142 = llvm.load %141 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%142, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %143 = llvm.extractvalue %71[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %144 = llvm.mlir.constant(128 : index) : i64
    %145 = llvm.mul %52, %144 : i64
    %146 = llvm.add %145, %36 : i64
    %147 = llvm.getelementptr %143[%146] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %148 = llvm.load %147 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%148, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %149 = llvm.extractvalue %71[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %150 = llvm.mlir.constant(128 : index) : i64
    %151 = llvm.mul %52, %150 : i64
    %152 = llvm.add %151, %35 : i64
    %153 = llvm.getelementptr %149[%152] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %154 = llvm.load %153 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%154, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%40, %41) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %155 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %156 = llvm.mlir.constant(32 : index) : i64
    %157 = llvm.mul %52, %156 : i64
    %158 = llvm.add %157, %52 : i64
    %159 = llvm.getelementptr %155[%158] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %160 = llvm.load %159 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%160, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %161 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %162 = llvm.mlir.constant(32 : index) : i64
    %163 = llvm.mul %52, %162 : i64
    %164 = llvm.add %163, %37 : i64
    %165 = llvm.getelementptr %161[%164] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %166 = llvm.load %165 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%166, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %167 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %168 = llvm.mlir.constant(32 : index) : i64
    %169 = llvm.mul %52, %168 : i64
    %170 = llvm.add %169, %36 : i64
    %171 = llvm.getelementptr %167[%170] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %172 = llvm.load %171 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%172, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %173 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %174 = llvm.mlir.constant(32 : index) : i64
    %175 = llvm.mul %52, %174 : i64
    %176 = llvm.add %175, %35 : i64
    %177 = llvm.getelementptr %173[%176] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %178 = llvm.load %177 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%178, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %179 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %180 = llvm.mlir.constant(32 : index) : i64
    %181 = llvm.mul %34, %180 : i64
    %182 = llvm.add %181, %52 : i64
    %183 = llvm.getelementptr %179[%182] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %184 = llvm.load %183 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%184, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %185 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %186 = llvm.mlir.constant(32 : index) : i64
    %187 = llvm.mul %34, %186 : i64
    %188 = llvm.add %187, %37 : i64
    %189 = llvm.getelementptr %185[%188] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %190 = llvm.load %189 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%190, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %191 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %192 = llvm.mlir.constant(32 : index) : i64
    %193 = llvm.mul %34, %192 : i64
    %194 = llvm.add %193, %36 : i64
    %195 = llvm.getelementptr %191[%194] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %196 = llvm.load %195 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%196, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %197 = llvm.extractvalue %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %198 = llvm.mlir.constant(32 : index) : i64
    %199 = llvm.mul %34, %198 : i64
    %200 = llvm.add %199, %35 : i64
    %201 = llvm.getelementptr %197[%200] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %202 = llvm.load %201 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%202, %41) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%41) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %203 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %204 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %205 = llvm.mlir.constant(128 : index) : i64
    %206 = llvm.mul %52, %205 : i64
    %207 = llvm.add %206, %52 : i64
    %208 = llvm.getelementptr %204[%207] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %209 = llvm.load %208 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %210 = llvm.fadd %209, %203  : vector<8xf32>
    %211 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %212 = llvm.mlir.constant(128 : index) : i64
    %213 = llvm.mul %52, %212 : i64
    %214 = llvm.add %213, %52 : i64
    %215 = llvm.getelementptr %211[%214] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %210, %215 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %216 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %217 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %218 = llvm.mlir.constant(128 : index) : i64
    %219 = llvm.mul %52, %218 : i64
    %220 = llvm.add %219, %37 : i64
    %221 = llvm.getelementptr %217[%220] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %222 = llvm.load %221 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %223 = llvm.fadd %222, %216  : vector<8xf32>
    %224 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %225 = llvm.mlir.constant(128 : index) : i64
    %226 = llvm.mul %52, %225 : i64
    %227 = llvm.add %226, %37 : i64
    %228 = llvm.getelementptr %224[%227] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %223, %228 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %229 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %230 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %231 = llvm.mlir.constant(128 : index) : i64
    %232 = llvm.mul %52, %231 : i64
    %233 = llvm.add %232, %36 : i64
    %234 = llvm.getelementptr %230[%233] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %235 = llvm.load %234 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %236 = llvm.fadd %235, %229  : vector<8xf32>
    %237 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %238 = llvm.mlir.constant(128 : index) : i64
    %239 = llvm.mul %52, %238 : i64
    %240 = llvm.add %239, %36 : i64
    %241 = llvm.getelementptr %237[%240] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %236, %241 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %242 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %243 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %244 = llvm.mlir.constant(128 : index) : i64
    %245 = llvm.mul %52, %244 : i64
    %246 = llvm.add %245, %35 : i64
    %247 = llvm.getelementptr %243[%246] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %248 = llvm.load %247 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %249 = llvm.fadd %248, %242  : vector<8xf32>
    %250 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %251 = llvm.mlir.constant(128 : index) : i64
    %252 = llvm.mul %52, %251 : i64
    %253 = llvm.add %252, %35 : i64
    %254 = llvm.getelementptr %250[%253] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %249, %254 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %255 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %256 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %257 = llvm.mlir.constant(128 : index) : i64
    %258 = llvm.mul %52, %257 : i64
    %259 = llvm.add %258, %33 : i64
    %260 = llvm.getelementptr %256[%259] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %261 = llvm.load %260 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %262 = llvm.fadd %261, %255  : vector<8xf32>
    %263 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %264 = llvm.mlir.constant(128 : index) : i64
    %265 = llvm.mul %52, %264 : i64
    %266 = llvm.add %265, %33 : i64
    %267 = llvm.getelementptr %263[%266] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %262, %267 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %268 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %269 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %270 = llvm.mlir.constant(128 : index) : i64
    %271 = llvm.mul %52, %270 : i64
    %272 = llvm.add %271, %32 : i64
    %273 = llvm.getelementptr %269[%272] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %274 = llvm.load %273 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %275 = llvm.fadd %274, %268  : vector<8xf32>
    %276 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %277 = llvm.mlir.constant(128 : index) : i64
    %278 = llvm.mul %52, %277 : i64
    %279 = llvm.add %278, %32 : i64
    %280 = llvm.getelementptr %276[%279] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %275, %280 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %281 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %282 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %283 = llvm.mlir.constant(128 : index) : i64
    %284 = llvm.mul %52, %283 : i64
    %285 = llvm.add %284, %31 : i64
    %286 = llvm.getelementptr %282[%285] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %287 = llvm.load %286 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %288 = llvm.fadd %287, %281  : vector<8xf32>
    %289 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %290 = llvm.mlir.constant(128 : index) : i64
    %291 = llvm.mul %52, %290 : i64
    %292 = llvm.add %291, %31 : i64
    %293 = llvm.getelementptr %289[%292] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %288, %293 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %294 = "vcix.v.i"(%41) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %295 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %296 = llvm.mlir.constant(128 : index) : i64
    %297 = llvm.mul %52, %296 : i64
    %298 = llvm.add %297, %30 : i64
    %299 = llvm.getelementptr %295[%298] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %300 = llvm.load %299 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %301 = llvm.fadd %300, %294  : vector<8xf32>
    %302 = llvm.extractvalue %80[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %303 = llvm.mlir.constant(128 : index) : i64
    %304 = llvm.mul %52, %303 : i64
    %305 = llvm.add %304, %30 : i64
    %306 = llvm.getelementptr %302[%305] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %301, %306 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %307 = llvm.add %90, %33 : i64
    llvm.br ^bb5(%307 : i64)
  ^bb16:  // pred: ^bb5
    %308 = llvm.mul %81, %20 : i64
    %309 = llvm.add %308, %83 : i64
    %310 = llvm.mul %52, %45 : i64
    %311 = llvm.add %310, %52 : i64
    %312 = llvm.getelementptr %72[%311] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %313 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %314 = llvm.getelementptr %313[%309] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %315 = llvm.ptrtoint %314 : !llvm.ptr to i64
    %316 = llvm.ptrtoint %312 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %39, %38 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %48, %43 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %48, %46 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 3, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %315, %316 : (i64, i64) -> ()
    %317 = llvm.add %83, %20 : i64
    llvm.br ^bb3(%317 : i64)
  ^bb17:  // pred: ^bb3
    %318 = llvm.add %81, %21 : i64
    llvm.br ^bb1(%318 : i64)
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

