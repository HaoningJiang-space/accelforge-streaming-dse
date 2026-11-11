module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<8 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<8 x array<32 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<32 x f32>>
  llvm.func @kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: !llvm.ptr, %arg6: !llvm.ptr, %arg7: i64, %arg8: i64, %arg9: i64, %arg10: !llvm.ptr, %arg11: !llvm.ptr, %arg12: i64, %arg13: i64, %arg14: i64) {
    %0 = llvm.mlir.constant(32 : index) : i64
    %1 = llvm.mlir.constant(128 : index) : i64
    %2 = llvm.mlir.constant(64 : index) : i64
    %3 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %4 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %5 = llvm.mlir.constant(32 : index) : i64
    %6 = llvm.mlir.constant(0 : index) : i64
    %7 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %8 = llvm.mlir.constant(3735928559 : index) : i64
    %9 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %10 = llvm.mlir.constant(8 : index) : i64
    %11 = llvm.mlir.constant(1 : index) : i64
    %12 = llvm.mlir.constant(0 : index) : i64
    %13 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %14 = llvm.mlir.constant(8 : i64) : i64
    %15 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %16 = llvm.mlir.constant(16 : index) : i64
    %17 = llvm.mlir.constant(8 : index) : i64
    %18 = llvm.mlir.constant(1 : index) : i64
    %19 = llvm.getelementptr %9[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<8 x f32>>
    %20 = llvm.inttoptr %8 : i64 to !llvm.ptr<1>
    %21 = llvm.insertvalue %20, %7[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %22 = llvm.insertvalue %19, %21[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %23 = llvm.insertvalue %6, %22[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %24 = llvm.insertvalue %16, %23[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %25 = llvm.insertvalue %17, %24[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %26 = llvm.insertvalue %17, %25[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %27 = llvm.insertvalue %18, %26[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %28 = llvm.getelementptr %4[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<8 x array<32 x f32>>
    %29 = llvm.inttoptr %8 : i64 to !llvm.ptr<1>
    %30 = llvm.insertvalue %29, %7[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.insertvalue %28, %30[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %32 = llvm.insertvalue %6, %31[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %33 = llvm.insertvalue %17, %32[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %34 = llvm.insertvalue %5, %33[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.insertvalue %5, %34[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %36 = llvm.insertvalue %18, %35[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.getelementptr %3[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<32 x f32>>
    %38 = llvm.inttoptr %8 : i64 to !llvm.ptr<1>
    %39 = llvm.insertvalue %38, %7[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.insertvalue %37, %39[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.insertvalue %6, %40[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %42 = llvm.insertvalue %16, %41[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %43 = llvm.insertvalue %5, %42[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.insertvalue %5, %43[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %18, %44[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%12 : i64)
  ^bb1(%46: i64):  // 2 preds: ^bb0, ^bb8
    %47 = llvm.icmp "slt" %46, %2 : i64
    llvm.cond_br %47, ^bb2, ^bb9
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%12 : i64)
  ^bb3(%48: i64):  // 2 preds: ^bb2, ^bb7
    %49 = llvm.icmp "slt" %48, %1 : i64
    llvm.cond_br %49, ^bb4, ^bb8
  ^bb4:  // pred: ^bb3
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "VectorCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %50 = llvm.extractvalue %45[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %51 = llvm.mlir.constant(32 : index) : i64
    %52 = llvm.mul %12, %51 : i64
    %53 = llvm.add %52, %12 : i64
    %54 = llvm.getelementptr %50[%53] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %15, %54 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.br ^bb5(%12 : i64)
  ^bb5(%55: i64):  // 2 preds: ^bb4, ^bb6
    %56 = llvm.icmp "slt" %55, %0 : i64
    llvm.cond_br %56, ^bb6, ^bb7
  ^bb6:  // pred: ^bb5
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulPreload"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %57 = llvm.extractvalue %36[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.mlir.constant(32 : index) : i64
    %59 = llvm.mul %12, %58 : i64
    %60 = llvm.add %59, %12 : i64
    %61 = llvm.getelementptr %57[%60] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %62 = llvm.load %61 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%62, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.iv"(%13, %14) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %63 = llvm.extractvalue %27[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %64 = llvm.mlir.constant(8 : index) : i64
    %65 = llvm.mul %12, %64 : i64
    %66 = llvm.add %65, %12 : i64
    %67 = llvm.getelementptr %63[%66] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %68 = llvm.load %67 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    "vcix.iv"(%68, %14) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %69 = llvm.extractvalue %27[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.mlir.constant(8 : index) : i64
    %71 = llvm.mul %11, %70 : i64
    %72 = llvm.add %71, %12 : i64
    %73 = llvm.getelementptr %69[%72] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %74 = llvm.load %73 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%74, %14) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%14) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %75 = "vcix.v.i"(%14) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %76 = llvm.extractvalue %45[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.mlir.constant(32 : index) : i64
    %78 = llvm.mul %12, %77 : i64
    %79 = llvm.add %78, %12 : i64
    %80 = llvm.getelementptr %76[%79] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %81 = llvm.load %80 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %82 = llvm.fadd %81, %75  : vector<8xf32>
    %83 = llvm.extractvalue %45[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %84 = llvm.mlir.constant(32 : index) : i64
    %85 = llvm.mul %12, %84 : i64
    %86 = llvm.add %85, %12 : i64
    %87 = llvm.getelementptr %83[%86] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %82, %87 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %88 = "vcix.v.i"(%14) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %89 = llvm.extractvalue %45[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %90 = llvm.mlir.constant(32 : index) : i64
    %91 = llvm.mul %12, %90 : i64
    %92 = llvm.add %91, %10 : i64
    %93 = llvm.getelementptr %89[%92] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %94 = llvm.load %93 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %95 = llvm.fadd %94, %88  : vector<8xf32>
    %96 = llvm.extractvalue %45[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %97 = llvm.mlir.constant(32 : index) : i64
    %98 = llvm.mul %12, %97 : i64
    %99 = llvm.add %98, %10 : i64
    %100 = llvm.getelementptr %96[%99] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %95, %100 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %101 = llvm.add %55, %0 : i64
    llvm.br ^bb5(%101 : i64)
  ^bb7:  // pred: ^bb5
    %102 = llvm.add %48, %1 : i64
    llvm.br ^bb3(%102 : i64)
  ^bb8:  // pred: ^bb3
    %103 = llvm.add %46, %2 : i64
    llvm.br ^bb1(%103 : i64)
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

