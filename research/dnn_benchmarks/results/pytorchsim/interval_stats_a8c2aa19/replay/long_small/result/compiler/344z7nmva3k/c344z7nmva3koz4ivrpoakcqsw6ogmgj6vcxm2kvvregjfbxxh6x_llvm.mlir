module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<16 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<128 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<128 x f32>>
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
    %18 = llvm.mlir.constant(12288 : index) : i64
    %19 = llvm.mlir.constant(49152 : index) : i64
    %20 = llvm.mlir.constant(1 : index) : i64
    %21 = llvm.mlir.constant(3072 : index) : i64
    %22 = llvm.mlir.constant(768 : index) : i64
    %23 = llvm.mlir.constant(16 : index) : i64
    %24 = llvm.mlir.constant(128 : index) : i64
    %25 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %26 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %27 = llvm.mlir.constant(0 : index) : i64
    %28 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %29 = llvm.mlir.constant(3735928559 : index) : i64
    %30 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %31 = llvm.mlir.constant(1 : index) : i64
    %32 = llvm.mlir.constant(8 : index) : i64
    %33 = llvm.mlir.constant(4295409668 : i64) : i64
    %34 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %35 = llvm.mlir.constant(8 : i64) : i64
    %36 = llvm.mlir.constant(3298534883329 : i64) : i64
    %37 = llvm.mlir.constant(281479272726656 : i64) : i64
    %38 = llvm.mlir.constant(128 : index) : i64
    %39 = llvm.mlir.constant(4294967312 : i64) : i64
    %40 = llvm.mlir.constant(13194139533313 : i64) : i64
    %41 = llvm.mlir.constant(0 : i64) : i64
    %42 = llvm.mlir.constant(4295016452 : i64) : i64
    %43 = llvm.mlir.constant(281479272726544 : i64) : i64
    %44 = llvm.mlir.constant(16 : index) : i64
    %45 = llvm.mlir.constant(0 : index) : i64
    %46 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %47 = llvm.getelementptr %30[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<16 x f32>>
    %48 = llvm.inttoptr %29 : i64 to !llvm.ptr<1>
    %49 = llvm.insertvalue %48, %28[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %50 = llvm.insertvalue %47, %49[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %51 = llvm.insertvalue %27, %50[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %52 = llvm.insertvalue %44, %51[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %53 = llvm.insertvalue %44, %52[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %54 = llvm.insertvalue %44, %53[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %55 = llvm.insertvalue %31, %54[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.getelementptr %26[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<128 x f32>>
    %57 = llvm.inttoptr %29 : i64 to !llvm.ptr<1>
    %58 = llvm.insertvalue %57, %28[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.insertvalue %56, %58[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %60 = llvm.insertvalue %27, %59[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.insertvalue %44, %60[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.insertvalue %38, %61[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %63 = llvm.insertvalue %38, %62[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.insertvalue %31, %63[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.getelementptr %25[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<128 x f32>>
    %66 = llvm.inttoptr %29 : i64 to !llvm.ptr<1>
    %67 = llvm.insertvalue %66, %28[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.insertvalue %65, %67[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.insertvalue %27, %68[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.insertvalue %44, %69[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.insertvalue %38, %70[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %72 = llvm.insertvalue %38, %71[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %73 = llvm.insertvalue %31, %72[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%45 : i64)
  ^bb1(%74: i64):  // 2 preds: ^bb0, ^bb17
    %75 = llvm.icmp "slt" %74, %24 : i64
    llvm.cond_br %75, ^bb2, ^bb18
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%45 : i64)
  ^bb3(%76: i64):  // 2 preds: ^bb2, ^bb16
    %77 = llvm.icmp "slt" %76, %22 : i64
    llvm.cond_br %77, ^bb4, ^bb17
  ^bb4:  // pred: ^bb3
    %78 = llvm.extractvalue %73[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %79 = llvm.mlir.constant(128 : index) : i64
    %80 = llvm.mul %45, %79 : i64
    %81 = llvm.add %80, %45 : i64
    %82 = llvm.getelementptr %78[%81] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %46, %82 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.br ^bb5(%45 : i64)
  ^bb5(%83: i64):  // 2 preds: ^bb4, ^bb15
    %84 = llvm.icmp "slt" %83, %21 : i64
    llvm.cond_br %84, ^bb6, ^bb16
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%45 : i64)
  ^bb7(%85: i64):  // 2 preds: ^bb6, ^bb14
    %86 = llvm.icmp "slt" %85, %20 : i64
    llvm.cond_br %86, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%45 : i64)
  ^bb9(%87: i64):  // 2 preds: ^bb8, ^bb13
    %88 = llvm.icmp "slt" %87, %20 : i64
    llvm.cond_br %88, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%45 : i64)
  ^bb11(%89: i64):  // 2 preds: ^bb10, ^bb12
    %90 = llvm.icmp "slt" %89, %20 : i64
    llvm.cond_br %90, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %91 = llvm.mul %85, %23 : i64
    %92 = llvm.mul %85, %19 : i64
    %93 = llvm.mul %87, %23 : i64
    %94 = llvm.add %92, %93 : i64
    %95 = llvm.mul %74, %21 : i64
    %96 = llvm.add %94, %95 : i64
    %97 = llvm.add %96, %83 : i64
    %98 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %99 = llvm.getelementptr %98[%97] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %100 = llvm.mul %45, %44 : i64
    %101 = llvm.add %100, %91 : i64
    %102 = llvm.getelementptr %47[%101] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %103 = llvm.ptrtoint %99 : !llvm.ptr to i64
    %104 = llvm.ptrtoint %102 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %43, %42 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %41, %40 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %41, %39 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %103, %104 : (i64, i64) -> ()
    %105 = llvm.mul %87, %23 : i64
    %106 = llvm.mul %89, %23 : i64
    %107 = llvm.add %105, %106 : i64
    %108 = llvm.mul %87, %18 : i64
    %109 = llvm.mul %89, %24 : i64
    %110 = llvm.add %108, %109 : i64
    %111 = llvm.mul %83, %22 : i64
    %112 = llvm.add %110, %111 : i64
    %113 = llvm.add %112, %76 : i64
    %114 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %115 = llvm.getelementptr %114[%113] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %116 = llvm.mul %45, %38 : i64
    %117 = llvm.add %116, %107 : i64
    %118 = llvm.getelementptr %56[%117] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %119 = llvm.ptrtoint %115 : !llvm.ptr to i64
    %120 = llvm.ptrtoint %118 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %37, %42 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %41, %36 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %41, %39 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %119, %120 : (i64, i64) -> ()
    %121 = llvm.add %89, %20 : i64
    llvm.br ^bb11(%121 : i64)
  ^bb13:  // pred: ^bb11
    %122 = llvm.add %87, %20 : i64
    llvm.br ^bb9(%122 : i64)
  ^bb14:  // pred: ^bb9
    %123 = llvm.add %85, %20 : i64
    llvm.br ^bb7(%123 : i64)
  ^bb15:  // pred: ^bb7
    %124 = llvm.extractvalue %64[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %125 = llvm.mlir.constant(128 : index) : i64
    %126 = llvm.mul %45, %125 : i64
    %127 = llvm.add %126, %45 : i64
    %128 = llvm.getelementptr %124[%127] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %129 = llvm.load %128 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%129, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %130 = llvm.extractvalue %64[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %131 = llvm.mlir.constant(128 : index) : i64
    %132 = llvm.mul %45, %131 : i64
    %133 = llvm.add %132, %32 : i64
    %134 = llvm.getelementptr %130[%133] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %135 = llvm.load %134 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%135, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%34, %35) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %136 = llvm.extractvalue %55[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %137 = llvm.mlir.constant(16 : index) : i64
    %138 = llvm.mul %45, %137 : i64
    %139 = llvm.add %138, %45 : i64
    %140 = llvm.getelementptr %136[%139] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %141 = llvm.load %140 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%141, %35) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %142 = llvm.extractvalue %55[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %143 = llvm.mlir.constant(16 : index) : i64
    %144 = llvm.mul %45, %143 : i64
    %145 = llvm.add %144, %32 : i64
    %146 = llvm.getelementptr %142[%145] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %147 = llvm.load %146 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%147, %35) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%35) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %148 = "vcix.v.i"(%35) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %149 = llvm.extractvalue %73[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %150 = llvm.mlir.constant(128 : index) : i64
    %151 = llvm.mul %45, %150 : i64
    %152 = llvm.add %151, %45 : i64
    %153 = llvm.getelementptr %149[%152] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %154 = llvm.load %153 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %155 = llvm.fadd %154, %148  : vector<8xf32>
    %156 = llvm.extractvalue %73[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %157 = llvm.mlir.constant(128 : index) : i64
    %158 = llvm.mul %45, %157 : i64
    %159 = llvm.add %158, %45 : i64
    %160 = llvm.getelementptr %156[%159] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %155, %160 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %161 = "vcix.v.i"(%35) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %162 = llvm.extractvalue %73[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %163 = llvm.mlir.constant(128 : index) : i64
    %164 = llvm.mul %45, %163 : i64
    %165 = llvm.add %164, %32 : i64
    %166 = llvm.getelementptr %162[%165] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %167 = llvm.load %166 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %168 = llvm.fadd %167, %161  : vector<8xf32>
    %169 = llvm.extractvalue %73[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %170 = llvm.mlir.constant(128 : index) : i64
    %171 = llvm.mul %45, %170 : i64
    %172 = llvm.add %171, %32 : i64
    %173 = llvm.getelementptr %169[%172] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %168, %173 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %174 = llvm.add %83, %23 : i64
    llvm.br ^bb5(%174 : i64)
  ^bb16:  // pred: ^bb5
    %175 = llvm.mul %74, %22 : i64
    %176 = llvm.add %175, %76 : i64
    %177 = llvm.mul %45, %38 : i64
    %178 = llvm.add %177, %45 : i64
    %179 = llvm.getelementptr %65[%178] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %180 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %181 = llvm.getelementptr %180[%176] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %182 = llvm.ptrtoint %181 : !llvm.ptr to i64
    %183 = llvm.ptrtoint %179 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %37, %33 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %41, %36 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %41, %39 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 3, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %182, %183 : (i64, i64) -> ()
    %184 = llvm.add %76, %24 : i64
    llvm.br ^bb3(%184 : i64)
  ^bb17:  // pred: ^bb3
    %185 = llvm.add %74, %23 : i64
    llvm.br ^bb1(%185 : i64)
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

