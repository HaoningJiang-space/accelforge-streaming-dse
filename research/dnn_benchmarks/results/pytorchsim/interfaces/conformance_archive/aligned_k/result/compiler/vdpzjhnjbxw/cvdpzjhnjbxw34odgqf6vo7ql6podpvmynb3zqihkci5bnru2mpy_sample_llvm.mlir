module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<256 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<256 x array<32 x f32>>
  llvm.mlir.global external @Y_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<32 x f32>>
  llvm.func @kernel(%arg0: !llvm.ptr, %arg1: !llvm.ptr, %arg2: i64, %arg3: i64, %arg4: i64, %arg5: !llvm.ptr, %arg6: !llvm.ptr, %arg7: i64, %arg8: i64, %arg9: i64, %arg10: !llvm.ptr, %arg11: !llvm.ptr, %arg12: i64, %arg13: i64, %arg14: i64) {
    %0 = llvm.mlir.constant(3 : index) : i64
    %1 = llvm.mlir.constant(1 : index) : i64
    %2 = llvm.mlir.constant(4 : index) : i64
    %3 = llvm.mlir.constant(2 : index) : i64
    %4 = llvm.mlir.constant(256 : index) : i64
    %5 = llvm.mlir.constant(32 : index) : i64
    %6 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %7 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %8 = llvm.mlir.constant(32 : index) : i64
    %9 = llvm.mlir.constant(0 : index) : i64
    %10 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %11 = llvm.mlir.constant(3735928559 : index) : i64
    %12 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %13 = llvm.mlir.constant(24 : index) : i64
    %14 = llvm.mlir.constant(16 : index) : i64
    %15 = llvm.mlir.constant(8 : index) : i64
    %16 = llvm.mlir.constant(0 : index) : i64
    %17 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %18 = llvm.mlir.constant(8 : i64) : i64
    %19 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %20 = llvm.mlir.constant(16 : index) : i64
    %21 = llvm.mlir.constant(256 : index) : i64
    %22 = llvm.mlir.constant(1 : index) : i64
    %23 = llvm.getelementptr %12[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<256 x f32>>
    %24 = llvm.inttoptr %11 : i64 to !llvm.ptr<1>
    %25 = llvm.insertvalue %24, %10[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %26 = llvm.insertvalue %23, %25[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %27 = llvm.insertvalue %9, %26[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %28 = llvm.insertvalue %20, %27[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %29 = llvm.insertvalue %21, %28[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %30 = llvm.insertvalue %21, %29[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %31 = llvm.insertvalue %22, %30[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %32 = llvm.getelementptr %7[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<256 x array<32 x f32>>
    %33 = llvm.inttoptr %11 : i64 to !llvm.ptr<1>
    %34 = llvm.insertvalue %33, %10[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %35 = llvm.insertvalue %32, %34[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %36 = llvm.insertvalue %9, %35[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %37 = llvm.insertvalue %21, %36[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %38 = llvm.insertvalue %8, %37[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %39 = llvm.insertvalue %8, %38[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %40 = llvm.insertvalue %22, %39[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %41 = llvm.getelementptr %6[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<32 x f32>>
    %42 = llvm.inttoptr %11 : i64 to !llvm.ptr<1>
    %43 = llvm.insertvalue %42, %10[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %44 = llvm.insertvalue %41, %43[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %45 = llvm.insertvalue %9, %44[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %46 = llvm.insertvalue %20, %45[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %47 = llvm.insertvalue %8, %46[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %48 = llvm.insertvalue %8, %47[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %49 = llvm.insertvalue %22, %48[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%16 : i64)
  ^bb1(%50: i64):  // 2 preds: ^bb0, ^bb11
    %51 = llvm.icmp "slt" %50, %14 : i64
    llvm.cond_br %51, ^bb2, ^bb12
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%16 : i64)
  ^bb3(%52: i64):  // 2 preds: ^bb2, ^bb10
    %53 = llvm.icmp "slt" %52, %5 : i64
    llvm.cond_br %53, ^bb4, ^bb11
  ^bb4:  // pred: ^bb3
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "VectorCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %54 = llvm.extractvalue %49[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %55 = llvm.mlir.constant(32 : index) : i64
    %56 = llvm.mul %16, %55 : i64
    %57 = llvm.add %56, %16 : i64
    %58 = llvm.getelementptr %54[%57] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %19, %58 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.br ^bb5(%16 : i64)
  ^bb5(%59: i64):  // 2 preds: ^bb4, ^bb9
    %60 = llvm.icmp "slt" %59, %4 : i64
    llvm.cond_br %60, ^bb6, ^bb10
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%16 : i64)
  ^bb7(%61: i64):  // 2 preds: ^bb6, ^bb8
    %62 = llvm.icmp "slt" %61, %3 : i64
    llvm.cond_br %62, ^bb8, ^bb9
  ^bb8:  // pred: ^bb7
    %63 = llvm.mul %61, %2 : i64
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulPreload"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %64 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.mlir.constant(32 : index) : i64
    %66 = llvm.mul %63, %65 : i64
    %67 = llvm.add %66, %16 : i64
    %68 = llvm.getelementptr %64[%67] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %69 = llvm.load %68 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%69, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %70 = llvm.mul %61, %2 : i64
    %71 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %72 = llvm.mlir.constant(32 : index) : i64
    %73 = llvm.mul %70, %72 : i64
    %74 = llvm.add %73, %15 : i64
    %75 = llvm.getelementptr %71[%74] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %76 = llvm.load %75 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%76, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %77 = llvm.mul %61, %2 : i64
    %78 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %79 = llvm.mlir.constant(32 : index) : i64
    %80 = llvm.mul %77, %79 : i64
    %81 = llvm.add %80, %14 : i64
    %82 = llvm.getelementptr %78[%81] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %83 = llvm.load %82 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%83, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %84 = llvm.mul %61, %2 : i64
    %85 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %86 = llvm.mlir.constant(32 : index) : i64
    %87 = llvm.mul %84, %86 : i64
    %88 = llvm.add %87, %13 : i64
    %89 = llvm.getelementptr %85[%88] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %90 = llvm.load %89 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%90, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %91 = llvm.mul %61, %2 : i64
    %92 = llvm.add %91, %1 : i64
    %93 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %94 = llvm.mlir.constant(32 : index) : i64
    %95 = llvm.mul %92, %94 : i64
    %96 = llvm.add %95, %16 : i64
    %97 = llvm.getelementptr %93[%96] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %98 = llvm.load %97 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%98, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %99 = llvm.mul %61, %2 : i64
    %100 = llvm.add %99, %1 : i64
    %101 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %102 = llvm.mlir.constant(32 : index) : i64
    %103 = llvm.mul %100, %102 : i64
    %104 = llvm.add %103, %15 : i64
    %105 = llvm.getelementptr %101[%104] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %106 = llvm.load %105 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%106, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %107 = llvm.mul %61, %2 : i64
    %108 = llvm.add %107, %1 : i64
    %109 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %110 = llvm.mlir.constant(32 : index) : i64
    %111 = llvm.mul %108, %110 : i64
    %112 = llvm.add %111, %14 : i64
    %113 = llvm.getelementptr %109[%112] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %114 = llvm.load %113 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%114, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %115 = llvm.mul %61, %2 : i64
    %116 = llvm.add %115, %1 : i64
    %117 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %118 = llvm.mlir.constant(32 : index) : i64
    %119 = llvm.mul %116, %118 : i64
    %120 = llvm.add %119, %13 : i64
    %121 = llvm.getelementptr %117[%120] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %122 = llvm.load %121 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%122, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %123 = llvm.mul %61, %2 : i64
    %124 = llvm.add %123, %3 : i64
    %125 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %126 = llvm.mlir.constant(32 : index) : i64
    %127 = llvm.mul %124, %126 : i64
    %128 = llvm.add %127, %16 : i64
    %129 = llvm.getelementptr %125[%128] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %130 = llvm.load %129 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%130, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %131 = llvm.mul %61, %2 : i64
    %132 = llvm.add %131, %3 : i64
    %133 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %134 = llvm.mlir.constant(32 : index) : i64
    %135 = llvm.mul %132, %134 : i64
    %136 = llvm.add %135, %15 : i64
    %137 = llvm.getelementptr %133[%136] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %138 = llvm.load %137 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%138, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %139 = llvm.mul %61, %2 : i64
    %140 = llvm.add %139, %3 : i64
    %141 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %142 = llvm.mlir.constant(32 : index) : i64
    %143 = llvm.mul %140, %142 : i64
    %144 = llvm.add %143, %14 : i64
    %145 = llvm.getelementptr %141[%144] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %146 = llvm.load %145 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%146, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %147 = llvm.mul %61, %2 : i64
    %148 = llvm.add %147, %3 : i64
    %149 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %150 = llvm.mlir.constant(32 : index) : i64
    %151 = llvm.mul %148, %150 : i64
    %152 = llvm.add %151, %13 : i64
    %153 = llvm.getelementptr %149[%152] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %154 = llvm.load %153 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%154, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %155 = llvm.mul %61, %2 : i64
    %156 = llvm.add %155, %0 : i64
    %157 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %158 = llvm.mlir.constant(32 : index) : i64
    %159 = llvm.mul %156, %158 : i64
    %160 = llvm.add %159, %16 : i64
    %161 = llvm.getelementptr %157[%160] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %162 = llvm.load %161 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%162, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %163 = llvm.mul %61, %2 : i64
    %164 = llvm.add %163, %0 : i64
    %165 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %166 = llvm.mlir.constant(32 : index) : i64
    %167 = llvm.mul %164, %166 : i64
    %168 = llvm.add %167, %15 : i64
    %169 = llvm.getelementptr %165[%168] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %170 = llvm.load %169 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%170, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %171 = llvm.mul %61, %2 : i64
    %172 = llvm.add %171, %0 : i64
    %173 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %174 = llvm.mlir.constant(32 : index) : i64
    %175 = llvm.mul %172, %174 : i64
    %176 = llvm.add %175, %14 : i64
    %177 = llvm.getelementptr %173[%176] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %178 = llvm.load %177 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%178, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %179 = llvm.mul %61, %2 : i64
    %180 = llvm.add %179, %0 : i64
    %181 = llvm.extractvalue %40[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %182 = llvm.mlir.constant(32 : index) : i64
    %183 = llvm.mul %180, %182 : i64
    %184 = llvm.add %183, %13 : i64
    %185 = llvm.getelementptr %181[%184] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %186 = llvm.load %185 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%186, %18) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %187 = llvm.mul %61, %14 : i64
    %188 = llvm.mlir.constant(1 : index) : i64
    %189 = llvm.mlir.constant(256 : index) : i64
    %190 = llvm.sub %189, %187 : i64
    %191 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %192 = llvm.trunc %190 : i64 to i32
    %193 = llvm.mlir.undef : vector<8xi32>
    %194 = llvm.mlir.constant(0 : i32) : i32
    %195 = llvm.insertelement %192, %193[%194 : i32] : vector<8xi32>
    %196 = llvm.shufflevector %195, %193 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %197 = llvm.icmp "sgt" %196, %191 : vector<8xi32>
    %198 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %199 = llvm.extractvalue %31[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %200 = llvm.mlir.constant(256 : index) : i64
    %201 = llvm.mul %16, %200 : i64
    %202 = llvm.add %201, %187 : i64
    %203 = llvm.getelementptr %199[%202] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %204 = llvm.intr.masked.load %203, %197, %198 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    llvm.inline_asm has_side_effects asm_dialect = att {compute_type = "MatmulCompute"} ".insn r CUSTOM_3, 0, 0x40, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    "vcix.iv"(%204, %18) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %205 = llvm.mul %61, %14 : i64
    %206 = llvm.add %205, %15 : i64
    %207 = llvm.mlir.constant(1 : index) : i64
    %208 = llvm.mlir.constant(256 : index) : i64
    %209 = llvm.sub %208, %206 : i64
    %210 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %211 = llvm.trunc %209 : i64 to i32
    %212 = llvm.mlir.undef : vector<8xi32>
    %213 = llvm.mlir.constant(0 : i32) : i32
    %214 = llvm.insertelement %211, %212[%213 : i32] : vector<8xi32>
    %215 = llvm.shufflevector %214, %212 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %216 = llvm.icmp "sgt" %215, %210 : vector<8xi32>
    %217 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %218 = llvm.extractvalue %31[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %219 = llvm.mlir.constant(256 : index) : i64
    %220 = llvm.mul %16, %219 : i64
    %221 = llvm.add %220, %206 : i64
    %222 = llvm.getelementptr %218[%221] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %223 = llvm.intr.masked.load %222, %216, %217 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    "vcix.iv"(%223, %18) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%18) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %224 = "vcix.v.i"(%18) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %225 = llvm.extractvalue %49[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %226 = llvm.mlir.constant(32 : index) : i64
    %227 = llvm.mul %16, %226 : i64
    %228 = llvm.add %227, %16 : i64
    %229 = llvm.getelementptr %225[%228] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %230 = llvm.load %229 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %231 = llvm.fadd %230, %224  : vector<8xf32>
    %232 = llvm.extractvalue %49[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %233 = llvm.mlir.constant(32 : index) : i64
    %234 = llvm.mul %16, %233 : i64
    %235 = llvm.add %234, %16 : i64
    %236 = llvm.getelementptr %232[%235] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %231, %236 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %237 = "vcix.v.i"(%18) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %238 = llvm.extractvalue %49[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %239 = llvm.mlir.constant(32 : index) : i64
    %240 = llvm.mul %16, %239 : i64
    %241 = llvm.add %240, %15 : i64
    %242 = llvm.getelementptr %238[%241] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %243 = llvm.load %242 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %244 = llvm.fadd %243, %237  : vector<8xf32>
    %245 = llvm.extractvalue %49[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %246 = llvm.mlir.constant(32 : index) : i64
    %247 = llvm.mul %16, %246 : i64
    %248 = llvm.add %247, %15 : i64
    %249 = llvm.getelementptr %245[%248] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %244, %249 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_3, 0, 0x41, x0, x0, x0", "~{a0},~{memory}"  : () -> ()
    %250 = llvm.add %61, %3 : i64
    llvm.br ^bb7(%250 : i64)
  ^bb9:  // pred: ^bb7
    %251 = llvm.add %59, %4 : i64
    llvm.br ^bb5(%251 : i64)
  ^bb10:  // pred: ^bb5
    %252 = llvm.add %52, %5 : i64
    llvm.br ^bb3(%252 : i64)
  ^bb11:  // pred: ^bb3
    %253 = llvm.add %50, %14 : i64
    llvm.br ^bb1(%253 : i64)
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

