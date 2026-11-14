module {
  llvm.mlir.global external @X_spad() {addr_space = 1 : i32} : !llvm.array<16 x array<256 x f32>>
  llvm.mlir.global external @W_spad() {addr_space = 1 : i32} : !llvm.array<256 x array<32 x f32>>
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
    %18 = llvm.mlir.constant(3 : index) : i64
    %19 = llvm.mlir.constant(4 : index) : i64
    %20 = llvm.mlir.constant(128 : index) : i64
    %21 = llvm.mlir.constant(4096 : index) : i64
    %22 = llvm.mlir.constant(2 : index) : i64
    %23 = llvm.mlir.constant(1 : index) : i64
    %24 = llvm.mlir.constant(256 : index) : i64
    %25 = llvm.mlir.constant(32 : index) : i64
    %26 = llvm.mlir.addressof @Y_spad : !llvm.ptr<1>
    %27 = llvm.mlir.addressof @W_spad : !llvm.ptr<1>
    %28 = llvm.mlir.constant(0 : index) : i64
    %29 = llvm.mlir.undef : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)>
    %30 = llvm.mlir.constant(3735928559 : index) : i64
    %31 = llvm.mlir.addressof @X_spad : !llvm.ptr<1>
    %32 = llvm.mlir.constant(1 : index) : i64
    %33 = llvm.mlir.constant(16 : index) : i64
    %34 = llvm.mlir.constant(24 : index) : i64
    %35 = llvm.mlir.constant(16 : index) : i64
    %36 = llvm.mlir.constant(8 : index) : i64
    %37 = llvm.mlir.constant(4295409668 : i64) : i64
    %38 = llvm.mlir.constant(281479272726560 : i64) : i64
    %39 = llvm.mlir.constant(0.000000e+00 : f32) : f32
    %40 = llvm.mlir.constant(8 : i64) : i64
    %41 = llvm.mlir.constant(4294967552 : i64) : i64
    %42 = llvm.mlir.constant(137438953473 : i64) : i64
    %43 = llvm.mlir.constant(281479280066592 : i64) : i64
    %44 = llvm.mlir.constant(32 : index) : i64
    %45 = llvm.mlir.constant(4294967312 : i64) : i64
    %46 = llvm.mlir.constant(1099511627777 : i64) : i64
    %47 = llvm.mlir.constant(0 : i64) : i64
    %48 = llvm.mlir.constant(4295016452 : i64) : i64
    %49 = llvm.mlir.constant(281479272726656 : i64) : i64
    %50 = llvm.mlir.constant(256 : index) : i64
    %51 = llvm.mlir.constant(0 : index) : i64
    %52 = llvm.mlir.constant(dense<0.000000e+00> : vector<16xf32>) : vector<16xf32>
    %53 = llvm.getelementptr %31[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<256 x f32>>
    %54 = llvm.inttoptr %30 : i64 to !llvm.ptr<1>
    %55 = llvm.insertvalue %54, %29[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %56 = llvm.insertvalue %53, %55[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %57 = llvm.insertvalue %28, %56[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %58 = llvm.insertvalue %33, %57[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %59 = llvm.insertvalue %50, %58[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %60 = llvm.insertvalue %50, %59[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %61 = llvm.insertvalue %32, %60[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %62 = llvm.getelementptr %27[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<256 x array<32 x f32>>
    %63 = llvm.inttoptr %30 : i64 to !llvm.ptr<1>
    %64 = llvm.insertvalue %63, %29[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %65 = llvm.insertvalue %62, %64[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %66 = llvm.insertvalue %28, %65[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %67 = llvm.insertvalue %50, %66[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %68 = llvm.insertvalue %44, %67[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %69 = llvm.insertvalue %44, %68[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %70 = llvm.insertvalue %32, %69[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %71 = llvm.getelementptr %26[0, 0, 0] : (!llvm.ptr<1>) -> !llvm.ptr<1>, !llvm.array<16 x array<32 x f32>>
    %72 = llvm.inttoptr %30 : i64 to !llvm.ptr<1>
    %73 = llvm.insertvalue %72, %29[0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %74 = llvm.insertvalue %71, %73[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %75 = llvm.insertvalue %28, %74[2] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %76 = llvm.insertvalue %33, %75[3, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %77 = llvm.insertvalue %44, %76[3, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %78 = llvm.insertvalue %44, %77[4, 0] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %79 = llvm.insertvalue %32, %78[4, 1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    llvm.br ^bb1(%51 : i64)
  ^bb1(%80: i64):  // 2 preds: ^bb0, ^bb20
    %81 = llvm.icmp "slt" %80, %35 : i64
    llvm.cond_br %81, ^bb2, ^bb21
  ^bb2:  // pred: ^bb1
    llvm.br ^bb3(%51 : i64)
  ^bb3(%82: i64):  // 2 preds: ^bb2, ^bb19
    %83 = llvm.icmp "slt" %82, %25 : i64
    llvm.cond_br %83, ^bb4, ^bb20
  ^bb4:  // pred: ^bb3
    %84 = llvm.extractvalue %79[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %85 = llvm.mlir.constant(32 : index) : i64
    %86 = llvm.mul %51, %85 : i64
    %87 = llvm.add %86, %51 : i64
    %88 = llvm.getelementptr %84[%87] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %52, %88 {alignment = 4 : i64} : vector<16xf32>, !llvm.ptr<1>
    llvm.br ^bb5(%51 : i64)
  ^bb5(%89: i64):  // 2 preds: ^bb4, ^bb18
    %90 = llvm.icmp "slt" %89, %24 : i64
    llvm.cond_br %90, ^bb6, ^bb19
  ^bb6:  // pred: ^bb5
    llvm.br ^bb7(%51 : i64)
  ^bb7(%91: i64):  // 2 preds: ^bb6, ^bb14
    %92 = llvm.icmp "slt" %91, %23 : i64
    llvm.cond_br %92, ^bb8, ^bb15
  ^bb8:  // pred: ^bb7
    llvm.br ^bb9(%51 : i64)
  ^bb9(%93: i64):  // 2 preds: ^bb8, ^bb13
    %94 = llvm.icmp "slt" %93, %22 : i64
    llvm.cond_br %94, ^bb10, ^bb14
  ^bb10:  // pred: ^bb9
    llvm.br ^bb11(%51 : i64)
  ^bb11(%95: i64):  // 2 preds: ^bb10, ^bb12
    %96 = llvm.icmp "slt" %95, %23 : i64
    llvm.cond_br %96, ^bb12, ^bb13
  ^bb12:  // pred: ^bb11
    %97 = llvm.mul %91, %35 : i64
    %98 = llvm.mul %93, %35 : i64
    %99 = llvm.add %97, %98 : i64
    %100 = llvm.mul %91, %21 : i64
    %101 = llvm.mul %93, %20 : i64
    %102 = llvm.add %100, %101 : i64
    %103 = llvm.mul %80, %24 : i64
    %104 = llvm.add %102, %103 : i64
    %105 = llvm.add %104, %89 : i64
    %106 = llvm.extractvalue %17[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %107 = llvm.getelementptr %106[%105] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %108 = llvm.mul %51, %50 : i64
    %109 = llvm.add %108, %99 : i64
    %110 = llvm.getelementptr %53[%109] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %111 = llvm.ptrtoint %107 : !llvm.ptr to i64
    %112 = llvm.ptrtoint %110 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %49, %48 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %47, %46 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %47, %45 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %111, %112 : (i64, i64) -> ()
    %113 = llvm.mul %93, %20 : i64
    %114 = llvm.mul %93, %21 : i64
    %115 = llvm.mul %95, %25 : i64
    %116 = llvm.add %114, %115 : i64
    %117 = llvm.mul %89, %25 : i64
    %118 = llvm.add %116, %117 : i64
    %119 = llvm.add %118, %82 : i64
    %120 = llvm.extractvalue %11[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %121 = llvm.getelementptr %120[%119] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %122 = llvm.mul %51, %44 : i64
    %123 = llvm.add %122, %113 : i64
    %124 = llvm.getelementptr %62[%123] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %125 = llvm.ptrtoint %121 : !llvm.ptr to i64
    %126 = llvm.ptrtoint %124 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %43, %48 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %47, %42 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %47, %41 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 2, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %125, %126 : (i64, i64) -> ()
    %127 = llvm.add %95, %23 : i64
    llvm.br ^bb11(%127 : i64)
  ^bb13:  // pred: ^bb11
    %128 = llvm.add %93, %23 : i64
    llvm.br ^bb9(%128 : i64)
  ^bb14:  // pred: ^bb9
    %129 = llvm.add %91, %23 : i64
    llvm.br ^bb7(%129 : i64)
  ^bb15:  // pred: ^bb7
    llvm.br ^bb16(%51 : i64)
  ^bb16(%130: i64):  // 2 preds: ^bb15, ^bb17
    %131 = llvm.icmp "slt" %130, %22 : i64
    llvm.cond_br %131, ^bb17, ^bb18
  ^bb17:  // pred: ^bb16
    %132 = llvm.mul %130, %19 : i64
    %133 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %134 = llvm.mlir.constant(32 : index) : i64
    %135 = llvm.mul %132, %134 : i64
    %136 = llvm.add %135, %51 : i64
    %137 = llvm.getelementptr %133[%136] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %138 = llvm.load %137 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%138, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %139 = llvm.mul %130, %19 : i64
    %140 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %141 = llvm.mlir.constant(32 : index) : i64
    %142 = llvm.mul %139, %141 : i64
    %143 = llvm.add %142, %36 : i64
    %144 = llvm.getelementptr %140[%143] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %145 = llvm.load %144 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%145, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %146 = llvm.mul %130, %19 : i64
    %147 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %148 = llvm.mlir.constant(32 : index) : i64
    %149 = llvm.mul %146, %148 : i64
    %150 = llvm.add %149, %35 : i64
    %151 = llvm.getelementptr %147[%150] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %152 = llvm.load %151 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%152, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %153 = llvm.mul %130, %19 : i64
    %154 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %155 = llvm.mlir.constant(32 : index) : i64
    %156 = llvm.mul %153, %155 : i64
    %157 = llvm.add %156, %34 : i64
    %158 = llvm.getelementptr %154[%157] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %159 = llvm.load %158 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%159, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %160 = llvm.mul %130, %19 : i64
    %161 = llvm.add %160, %23 : i64
    %162 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %163 = llvm.mlir.constant(32 : index) : i64
    %164 = llvm.mul %161, %163 : i64
    %165 = llvm.add %164, %51 : i64
    %166 = llvm.getelementptr %162[%165] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %167 = llvm.load %166 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%167, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %168 = llvm.mul %130, %19 : i64
    %169 = llvm.add %168, %23 : i64
    %170 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %171 = llvm.mlir.constant(32 : index) : i64
    %172 = llvm.mul %169, %171 : i64
    %173 = llvm.add %172, %36 : i64
    %174 = llvm.getelementptr %170[%173] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %175 = llvm.load %174 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%175, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %176 = llvm.mul %130, %19 : i64
    %177 = llvm.add %176, %23 : i64
    %178 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %179 = llvm.mlir.constant(32 : index) : i64
    %180 = llvm.mul %177, %179 : i64
    %181 = llvm.add %180, %35 : i64
    %182 = llvm.getelementptr %178[%181] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %183 = llvm.load %182 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%183, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %184 = llvm.mul %130, %19 : i64
    %185 = llvm.add %184, %23 : i64
    %186 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %187 = llvm.mlir.constant(32 : index) : i64
    %188 = llvm.mul %185, %187 : i64
    %189 = llvm.add %188, %34 : i64
    %190 = llvm.getelementptr %186[%189] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %191 = llvm.load %190 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%191, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %192 = llvm.mul %130, %19 : i64
    %193 = llvm.add %192, %22 : i64
    %194 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %195 = llvm.mlir.constant(32 : index) : i64
    %196 = llvm.mul %193, %195 : i64
    %197 = llvm.add %196, %51 : i64
    %198 = llvm.getelementptr %194[%197] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %199 = llvm.load %198 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%199, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %200 = llvm.mul %130, %19 : i64
    %201 = llvm.add %200, %22 : i64
    %202 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %203 = llvm.mlir.constant(32 : index) : i64
    %204 = llvm.mul %201, %203 : i64
    %205 = llvm.add %204, %36 : i64
    %206 = llvm.getelementptr %202[%205] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %207 = llvm.load %206 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%207, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %208 = llvm.mul %130, %19 : i64
    %209 = llvm.add %208, %22 : i64
    %210 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %211 = llvm.mlir.constant(32 : index) : i64
    %212 = llvm.mul %209, %211 : i64
    %213 = llvm.add %212, %35 : i64
    %214 = llvm.getelementptr %210[%213] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %215 = llvm.load %214 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%215, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %216 = llvm.mul %130, %19 : i64
    %217 = llvm.add %216, %22 : i64
    %218 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %219 = llvm.mlir.constant(32 : index) : i64
    %220 = llvm.mul %217, %219 : i64
    %221 = llvm.add %220, %34 : i64
    %222 = llvm.getelementptr %218[%221] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %223 = llvm.load %222 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%223, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %224 = llvm.mul %130, %19 : i64
    %225 = llvm.add %224, %18 : i64
    %226 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %227 = llvm.mlir.constant(32 : index) : i64
    %228 = llvm.mul %225, %227 : i64
    %229 = llvm.add %228, %51 : i64
    %230 = llvm.getelementptr %226[%229] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %231 = llvm.load %230 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%231, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %232 = llvm.mul %130, %19 : i64
    %233 = llvm.add %232, %18 : i64
    %234 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %235 = llvm.mlir.constant(32 : index) : i64
    %236 = llvm.mul %233, %235 : i64
    %237 = llvm.add %236, %36 : i64
    %238 = llvm.getelementptr %234[%237] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %239 = llvm.load %238 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%239, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %240 = llvm.mul %130, %19 : i64
    %241 = llvm.add %240, %18 : i64
    %242 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %243 = llvm.mlir.constant(32 : index) : i64
    %244 = llvm.mul %241, %243 : i64
    %245 = llvm.add %244, %35 : i64
    %246 = llvm.getelementptr %242[%245] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %247 = llvm.load %246 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%247, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %248 = llvm.mul %130, %19 : i64
    %249 = llvm.add %248, %18 : i64
    %250 = llvm.extractvalue %70[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %251 = llvm.mlir.constant(32 : index) : i64
    %252 = llvm.mul %249, %251 : i64
    %253 = llvm.add %252, %34 : i64
    %254 = llvm.getelementptr %250[%253] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %255 = llvm.load %254 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    "vcix.iv"(%255, %40) <{imm = 0 : i64, opcode = 1 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %256 = llvm.mul %130, %35 : i64
    %257 = llvm.mlir.constant(1 : index) : i64
    %258 = llvm.mlir.constant(256 : index) : i64
    %259 = llvm.sub %258, %256 : i64
    %260 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %261 = llvm.trunc %259 : i64 to i32
    %262 = llvm.mlir.undef : vector<8xi32>
    %263 = llvm.mlir.constant(0 : i32) : i32
    %264 = llvm.insertelement %261, %262[%263 : i32] : vector<8xi32>
    %265 = llvm.shufflevector %264, %262 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %266 = llvm.icmp "sgt" %265, %260 : vector<8xi32>
    %267 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %268 = llvm.extractvalue %61[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %269 = llvm.mlir.constant(256 : index) : i64
    %270 = llvm.mul %51, %269 : i64
    %271 = llvm.add %270, %256 : i64
    %272 = llvm.getelementptr %268[%271] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %273 = llvm.intr.masked.load %272, %266, %267 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    "vcix.iv"(%273, %40) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    %274 = llvm.mul %130, %35 : i64
    %275 = llvm.add %274, %36 : i64
    %276 = llvm.mlir.constant(1 : index) : i64
    %277 = llvm.mlir.constant(256 : index) : i64
    %278 = llvm.sub %277, %275 : i64
    %279 = llvm.mlir.constant(dense<[0, 1, 2, 3, 4, 5, 6, 7]> : vector<8xi32>) : vector<8xi32>
    %280 = llvm.trunc %278 : i64 to i32
    %281 = llvm.mlir.undef : vector<8xi32>
    %282 = llvm.mlir.constant(0 : i32) : i32
    %283 = llvm.insertelement %280, %281[%282 : i32] : vector<8xi32>
    %284 = llvm.shufflevector %283, %281 [0, 0, 0, 0, 0, 0, 0, 0] : vector<8xi32> 
    %285 = llvm.icmp "sgt" %284, %279 : vector<8xi32>
    %286 = llvm.mlir.constant(dense<0.000000e+00> : vector<8xf32>) : vector<8xf32>
    %287 = llvm.extractvalue %61[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %288 = llvm.mlir.constant(256 : index) : i64
    %289 = llvm.mul %51, %288 : i64
    %290 = llvm.add %289, %275 : i64
    %291 = llvm.getelementptr %287[%290] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %292 = llvm.intr.masked.load %291, %285, %286 {alignment = 4 : i32} : (!llvm.ptr<1>, vector<8xi1>, vector<8xf32>) -> vector<8xf32>
    "vcix.iv"(%292, %40) <{imm = 0 : i64, opcode = 0 : i64, rd = 0 : i64}> : (vector<8xf32>, i64) -> ()
    "vcix.i"(%40) <{imm = 4 : i64, lmul = 0 : i64, opcode = 1 : i64, rd = 0 : i64, rs2 = 0 : i64, sew = 32 : i64}> : (i64) -> ()
    %293 = "vcix.v.i"(%40) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %294 = llvm.extractvalue %79[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %295 = llvm.mlir.constant(32 : index) : i64
    %296 = llvm.mul %51, %295 : i64
    %297 = llvm.add %296, %51 : i64
    %298 = llvm.getelementptr %294[%297] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %299 = llvm.load %298 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %300 = llvm.fadd %299, %293  : vector<8xf32>
    %301 = llvm.extractvalue %79[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %302 = llvm.mlir.constant(32 : index) : i64
    %303 = llvm.mul %51, %302 : i64
    %304 = llvm.add %303, %51 : i64
    %305 = llvm.getelementptr %301[%304] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %300, %305 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %306 = "vcix.v.i"(%40) <{imm = 0 : i64, opcode = 2 : i64, rs2 = 0 : i64}> : (i64) -> vector<8xf32>
    %307 = llvm.extractvalue %79[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %308 = llvm.mlir.constant(32 : index) : i64
    %309 = llvm.mul %51, %308 : i64
    %310 = llvm.add %309, %36 : i64
    %311 = llvm.getelementptr %307[%310] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %312 = llvm.load %311 {alignment = 4 : i64} : !llvm.ptr<1> -> vector<8xf32>
    %313 = llvm.fadd %312, %306  : vector<8xf32>
    %314 = llvm.extractvalue %79[1] : !llvm.struct<(ptr<1>, ptr<1>, i64, array<2 x i64>, array<2 x i64>)> 
    %315 = llvm.mlir.constant(32 : index) : i64
    %316 = llvm.mul %51, %315 : i64
    %317 = llvm.add %316, %36 : i64
    %318 = llvm.getelementptr %314[%317] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    llvm.store %313, %318 {alignment = 4 : i64} : vector<8xf32>, !llvm.ptr<1>
    %319 = llvm.add %130, %23 : i64
    llvm.br ^bb16(%319 : i64)
  ^bb18:  // pred: ^bb16
    %320 = llvm.add %89, %24 : i64
    llvm.br ^bb5(%320 : i64)
  ^bb19:  // pred: ^bb5
    %321 = llvm.mul %80, %25 : i64
    %322 = llvm.add %321, %82 : i64
    %323 = llvm.mul %51, %44 : i64
    %324 = llvm.add %323, %51 : i64
    %325 = llvm.getelementptr %71[%324] : (!llvm.ptr<1>, i64) -> !llvm.ptr<1>, f32
    %326 = llvm.extractvalue %5[1] : !llvm.struct<(ptr, ptr, i64, array<1 x i64>, array<1 x i64>)> 
    %327 = llvm.getelementptr %326[%322] : (!llvm.ptr, i64) -> !llvm.ptr, f32
    %328 = llvm.ptrtoint %327 : !llvm.ptr to i64
    %329 = llvm.ptrtoint %325 : !llvm.ptr<1> to i64
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 0, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %38, %37 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 4, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %47, %42 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 5, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %47, %45 : (i64, i64) -> ()
    llvm.inline_asm has_side_effects asm_dialect = att ".insn r CUSTOM_1, 0x3, 3, x0, $0, $1", "r,r,~{dirflag},~{fpsr},~{flags}" %328, %329 : (i64, i64) -> ()
    %330 = llvm.add %82, %25 : i64
    llvm.br ^bb3(%330 : i64)
  ^bb20:  // pred: ^bb3
    %331 = llvm.add %80, %35 : i64
    llvm.br ^bb1(%331 : i64)
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

