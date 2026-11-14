module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<16 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<128 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<128 x f32>>
  llvm.func @kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: !llvm.ptr, %arg6: !llvm.ptr, %arg7: i64, %arg8: i64, %arg9: i64, %arg10: !llvm.ptr, %arg11: !llvm.ptr, %arg12: i64, %arg13: i64, %arg14: i64) {
    %0 = llvm.mlir.constant(3072 : index) : i64
    %1 = llvm.mlir.constant(768 : index) : i64
    %2 = llvm.mlir.constant(128 : index) : i64
    %3 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %4 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %5 = llvm.mlir.constant(128 : index) : i64
    %6 = llvm.mlir.constant(0 : index) : i64
    %7 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %8 = llvm.mlir.constant(3735928559 : index) : i64
    %9 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %10 = llvm.mlir.constant(8 : index) : i64
    %11 = llvm.mlir.constant(0 : index) : i64
    %12 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %13 = llvm.mlir.constant(8 : i64) : i64
    %14 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %15 = llvm.mlir.constant(16 : index) : i64
    %16 = llvm.mlir.constant(1 : index) : i64
    %17 = llvm.getelementptr %9[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<16 x f32>>
    %18 = llvm.inttoptr %8 : i64 to !llvm.ptr<1>
    %19 = llvm.insertvalue %18, %7[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %20 = llvm.insertvalue %17, %19[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %21 = llvm.insertvalue %6, %20[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %15, %21[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %15, %22[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = llvm.insertvalue %15, %23[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %25 = llvm.insertvalue %16, %24[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %26 = llvm.getelementptr %4[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<128 x f32>>
    %27 = llvm.inttoptr %8 : i64 to !llvm.ptr<1>
    %28 = llvm.insertvalue %27, %7[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %29 = llvm.insertvalue %26, %28[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = llvm.insertvalue %6, %29[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.insertvalue %15, %30[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %32 = llvm.insertvalue %5, %31[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %33 = llvm.insertvalue %5, %32[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %34 = llvm.insertvalue %16, %33[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.getelementptr %3[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<128 x f32>>
    %36 = llvm.inttoptr %8 : i64 to !llvm.ptr<1>
    %37 = llvm.insertvalue %36, %7[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %38 = llvm.insertvalue %35, %37[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %6, %38[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.insertvalue %15, %39[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.insertvalue %5, %40[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.insertvalue %5, %41[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.insertvalue %16, %42[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%11 : i64)
  ^bb1(%44: i64):  // 2 preds: ^bb0, ^bb8
    %45 = llvm.icmp "slt" %44, %2 : i64
    llvm.cond_br %45, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%11 : i64)
  ^bb3(%46: i64):  // 2 preds: ^bb2, ^bb7
    %47 = llvm.icmp "slt" %46, %1 : i64
    llvm.cond_br %47, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "VectorCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %48 = llvm.extractvalue %43[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %49 = llvm.mlir.constant(128 : index) : i64
    %50 = llvm.mul %11, %49 : i64
    %51 = llvm.add %50, %11 : i64
    %52 = llvm.getelementptr %48[%51] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %14, %52 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.br ^bb5(%11 : i64)
  ^bb5(%53: i64):  // 2 preds: ^bb4, ^bb6
    %54 = llvm.icmp "slt" %53, %0 : i64
    llvm.cond_br %54, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulPreload"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %55 = llvm.extractvalue %34[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.mlir.constant(128 : index) : i64
    %57 = llvm.mul %11, %56 : i64
    %58 = llvm.add %57, %11 : i64
    %59 = llvm.getelementptr %55[%58] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %60 = llvm.load %59 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%60, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %61 = llvm.extractvalue %34[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.mlir.constant(128 : index) : i64
    %63 = llvm.mul %11, %62 : i64
    %64 = llvm.add %63, %10 : i64
    %65 = llvm.getelementptr %61[%64] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %66 = llvm.load %65 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%66, %13) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
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
    %67 = llvm.extractvalue %25[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.mlir.constant(16 : index) : i64
    %69 = llvm.mul %11, %68 : i64
    %70 = llvm.add %69, %11 : i64
    %71 = llvm.getelementptr %67[%70] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %72 = llvm.load %71 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    "vcix.iv"(%72, %13) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %73 = llvm.extractvalue %25[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.mlir.constant(16 : index) : i64
    %75 = llvm.mul %11, %74 : i64
    %76 = llvm.add %75, %10 : i64
    %77 = llvm.getelementptr %73[%76] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %78 = llvm.load %77 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%78, %13) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%13) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %79 = "vcix.v.i"(%13) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %80 = llvm.extractvalue %43[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %81 = llvm.mlir.constant(128 : index) : i64
    %82 = llvm.mul %11, %81 : i64
    %83 = llvm.add %82, %11 : i64
    %84 = llvm.getelementptr %80[%83] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %85 = llvm.load %84 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %86 = llvm.fadd %85, %79  : vector<8xf32>
    %87 = llvm.extractvalue %43[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %88 = llvm.mlir.constant(128 : index) : i64
    %89 = llvm.mul %11, %88 : i64
    %90 = llvm.add %89, %11 : i64
    %91 = llvm.getelementptr %87[%90] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %86, %91 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %92 = "vcix.v.i"(%13) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %93 = llvm.extractvalue %43[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %94 = llvm.mlir.constant(128 : index) : i64
    %95 = llvm.mul %11, %94 : i64
    %96 = llvm.add %95, %10 : i64
    %97 = llvm.getelementptr %93[%96] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %98 = llvm.load %97 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %99 = llvm.fadd %98, %92  : vector<8xf32>
    %100 = llvm.extractvalue %43[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %101 = llvm.mlir.constant(128 : index) : i64
    %102 = llvm.mul %11, %101 : i64
    %103 = llvm.add %102, %10 : i64
    %104 = llvm.getelementptr %100[%103] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %99, %104 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %105 = llvm.add %53, %0 : i64
    llvm.br ^bb5(%105 : i64)
  ^bb7:  // pred: ^bb5
    %106 = llvm.add %46, %1 : i64
    llvm.br ^bb3(%106 : i64)
  ^bb8:  // pred: ^bb3
    %107 = llvm.add %44, %2 : i64
    llvm.br ^bb1(%107 : i64)
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

