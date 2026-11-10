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
    %20 = llvm.mlir.constant(2 : index) : i64
    %21 = llvm.mlir.constant(32 : index) : i64
    %22 = llvm.mlir.constant(128 : index) : i64
    %23 = llvm.mlir.constant(16 : index) : i64
    %24 = llvm.mlir.constant(64 : index) : i64
    %25 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %26 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %27 = llvm.mlir.constant(0 : index) : i64
    %28 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %29 = llvm.mlir.constant(3735928559 : index) : i64
    %30 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %31 = llvm.mlir.constant(1 : index) : i64
    %32 = llvm.mlir.constant(16 : index) : i64
    %33 = llvm.mlir.constant(8 : index) : i64
    %34 = llvm.mlir.constant(1 : index) : i64
    %35 = llvm.mlir.constant(4295409668 : i64) : i64
    %36 = llvm.mlir.constant(281479272726560 : i64) : i64
    %37 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %38 = llvm.mlir.constant(8 : i64) : i64
    %39 = llvm.mlir.constant(4294967304 : i64) : i64
    %40 = llvm.mlir.constant(549755813889 : i64) : i64
    %41 = llvm.mlir.constant(281479272202256 : i64) : i64
    %42 = llvm.mlir.constant(32 : index) : i64
    %43 = llvm.mlir.constant(4294967312 : i64) : i64
    %44 = llvm.mlir.constant(137438953473 : i64) : i64
    %45 = llvm.mlir.constant(0 : i64) : i64
    %46 = llvm.mlir.constant(4295016452 : i64) : i64
    %47 = llvm.mlir.constant(281479272726536 : i64) : i64
    %48 = llvm.mlir.constant(8 : index) : i64
    %49 = llvm.mlir.constant(0 : index) : i64
    %50 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %51 = llvm.getelementptr %30[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<8 x f32>>
    %52 = llvm.inttoptr %29 : i64 to !llvm.ptr<1>
    %53 = llvm.insertvalue %52, %28[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %54 = llvm.insertvalue %51, %53[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %55 = llvm.insertvalue %27, %54[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.insertvalue %32, %55[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %57 = llvm.insertvalue %48, %56[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.insertvalue %48, %57[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.insertvalue %31, %58[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %60 = llvm.getelementptr %26[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<8 x array<32 x f32>>
    %61 = llvm.inttoptr %29 : i64 to !llvm.ptr<1>
    %62 = llvm.insertvalue %61, %28[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.insertvalue %60, %62[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.insertvalue %27, %63[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.insertvalue %48, %64[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %66 = llvm.insertvalue %42, %65[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %67 = llvm.insertvalue %42, %66[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.insertvalue %31, %67[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.getelementptr %25[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<32 x f32>>
    %70 = llvm.inttoptr %29 : i64 to !llvm.ptr<1>
    %71 = llvm.insertvalue %70, %28[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %72 = llvm.insertvalue %69, %71[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %73 = llvm.insertvalue %27, %72[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.insertvalue %32, %73[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.insertvalue %42, %74[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.insertvalue %42, %75[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.insertvalue %31, %76[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%49 : i64)
  ^bb1(%78: i64):  // 2 preds: ^bb0, ^bb17
    %79 = llvm.icmp "slt" %78, %24 : i64
    llvm.cond_br %79, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%49 : i64)
  ^bb3(%80: i64):  // 2 preds: ^bb2, ^bb16
    %81 = llvm.icmp "slt" %80, %22 : i64
    llvm.cond_br %81, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    %82 = llvm.extractvalue %77[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %83 = llvm.mlir.constant(32 : index) : i64
    %84 = llvm.mul %49, %83 : i64
    %85 = llvm.add %84, %49 : i64
    %86 = llvm.getelementptr %82[%85] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %50, %86 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.br ^bb5(%49 : i64)
  ^bb5(%87: i64):  // 2 preds: ^bb4, ^bb15
    %88 = llvm.icmp "slt" %87, %21 : i64
    llvm.cond_br %88, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%49 : i64)
  ^bb7(%89: i64):  // 2 preds: ^bb6, ^bb14
    %90 = llvm.icmp "slt" %89, %34 : i64
    llvm.cond_br %90, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%49 : i64)
  ^bb9(%91: i64):  // 2 preds: ^bb8, ^bb13
    %92 = llvm.icmp "slt" %91, %34 : i64
    llvm.cond_br %92, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%49 : i64)
  ^bb11(%93: i64):  // 2 preds: ^bb10, ^bb12
    %94 = llvm.icmp "slt" %93, %20 : i64
    llvm.cond_br %94, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %95 = llvm.mul %89, %23 : i64
    %96 = llvm.mul %89, %19 : i64
    %97 = llvm.mul %91, %33 : i64
    %98 = llvm.add %96, %97 : i64
    %99 = llvm.mul %78, %21 : i64
    %100 = llvm.add %98, %99 : i64
    %101 = llvm.add %100, %87 : i64
    %102 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %103 = llvm.getelementptr %102[%101] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %104 = llvm.mul %49, %48 : i64
    %105 = llvm.add %104, %95 : i64
    %106 = llvm.getelementptr %51[%105] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %107 = llvm.ptrtoint %103 : !llvm.ptr to i64
    %108 = llvm.ptrtoint %106 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %47, %46 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %45, %44 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %45, %43 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %107, %108 : (i64, i64) -> ()
    %109 = llvm.mul %91, %33 : i64
    %110 = llvm.mul %91, %18 : i64
    %111 = llvm.mul %93, %23 : i64
    %112 = llvm.add %110, %111 : i64
    %113 = llvm.mul %87, %22 : i64
    %114 = llvm.add %112, %113 : i64
    %115 = llvm.add %114, %80 : i64
    %116 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %117 = llvm.getelementptr %116[%115] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %118 = llvm.mul %49, %42 : i64
    %119 = llvm.add %118, %109 : i64
    %120 = llvm.getelementptr %60[%119] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %121 = llvm.ptrtoint %117 : !llvm.ptr to i64
    %122 = llvm.ptrtoint %120 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %41, %46 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %45, %40 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %45, %39 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %121, %122 : (i64, i64) -> ()
    %123 = llvm.add %93, %34 : i64
    llvm.br ^bb11(%123 : i64)
  ^bb13:  // pred: ^bb11
    %124 = llvm.add %91, %34 : i64
    llvm.br ^bb9(%124 : i64)
  ^bb14:  // pred: ^bb9
    %125 = llvm.add %89, %34 : i64
    llvm.br ^bb7(%125 : i64)
  ^bb15:  // pred: ^bb7
    %126 = llvm.extractvalue %68[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %127 = llvm.mlir.constant(32 : index) : i64
    %128 = llvm.mul %49, %127 : i64
    %129 = llvm.add %128, %49 : i64
    %130 = llvm.getelementptr %126[%129] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %131 = llvm.load %130 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%131, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%37, %38) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %132 = llvm.extractvalue %59[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %133 = llvm.mlir.constant(8 : index) : i64
    %134 = llvm.mul %49, %133 : i64
    %135 = llvm.add %134, %49 : i64
    %136 = llvm.getelementptr %132[%135] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %137 = llvm.load %136 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%137, %38) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %138 = llvm.extractvalue %59[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %139 = llvm.mlir.constant(8 : index) : i64
    %140 = llvm.mul %34, %139 : i64
    %141 = llvm.add %140, %49 : i64
    %142 = llvm.getelementptr %138[%141] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %143 = llvm.load %142 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%143, %38) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%38) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %144 = "vcix.v.i"(%38) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %145 = llvm.extractvalue %77[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %146 = llvm.mlir.constant(32 : index) : i64
    %147 = llvm.mul %49, %146 : i64
    %148 = llvm.add %147, %49 : i64
    %149 = llvm.getelementptr %145[%148] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %150 = llvm.load %149 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %151 = llvm.fadd %150, %144  : vector<8xf32>
    %152 = llvm.extractvalue %77[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %153 = llvm.mlir.constant(32 : index) : i64
    %154 = llvm.mul %49, %153 : i64
    %155 = llvm.add %154, %49 : i64
    %156 = llvm.getelementptr %152[%155] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %151, %156 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %157 = "vcix.v.i"(%38) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %158 = llvm.extractvalue %77[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %159 = llvm.mlir.constant(32 : index) : i64
    %160 = llvm.mul %49, %159 : i64
    %161 = llvm.add %160, %33 : i64
    %162 = llvm.getelementptr %158[%161] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %163 = llvm.load %162 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %164 = llvm.fadd %163, %157  : vector<8xf32>
    %165 = llvm.extractvalue %77[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %166 = llvm.mlir.constant(32 : index) : i64
    %167 = llvm.mul %49, %166 : i64
    %168 = llvm.add %167, %33 : i64
    %169 = llvm.getelementptr %165[%168] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %164, %169 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %170 = llvm.add %87, %33 : i64
    llvm.br ^bb5(%170 : i64)
  ^bb16:  // pred: ^bb5
    %171 = llvm.mul %78, %22 : i64
    %172 = llvm.add %171, %80 : i64
    %173 = llvm.mul %49, %42 : i64
    %174 = llvm.add %173, %49 : i64
    %175 = llvm.getelementptr %69[%174] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %176 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %177 = llvm.getelementptr %176[%172] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %178 = llvm.ptrtoint %177 : !llvm.ptr to i64
    %179 = llvm.ptrtoint %175 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %36, %35 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %45, %40 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %45, %43 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 3, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %178, %179 : (i64, i64) -> ()
    %180 = llvm.add %80, %21 : i64
    llvm.br ^bb3(%180 : i64)
  ^bb17:  // pred: ^bb3
    %181 = llvm.add %78, %23 : i64
    llvm.br ^bb1(%181 : i64)
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

