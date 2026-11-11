	.text
	.attribute	4, 16
	.attribute	5, "rv64i2p1_m2p0_a2p1_f2p2_d2p2_c2p0_v1p0_zicsr2p0_zmmul1p0_zfhmin1p0_zve32f1p0_zve32x1p0_zve64d1p0_zve64f1p0_zve64x1p0_zvfh1p0_zvfhmin1p0_zvl128b1p0_zvl256b1p0_zvl32b1p0_zvl64b1p0_xsfvcp1p0"
	.file	"LLVMDialectModule"
	.globl	kernel                          # -- Begin function kernel
	.p2align	1
	.type	kernel,@function
kernel:                                 # @kernel
.Lfunc_begin0:
	.cfi_startproc
# %bb.0:
	addi	sp, sp, -160
	.cfi_def_cfa_offset 160
	sd	ra, 152(sp)                     # 8-byte Folded Spill
	sd	s0, 144(sp)                     # 8-byte Folded Spill
	sd	s1, 136(sp)                     # 8-byte Folded Spill
	sd	s2, 128(sp)                     # 8-byte Folded Spill
	sd	s3, 120(sp)                     # 8-byte Folded Spill
	sd	s4, 112(sp)                     # 8-byte Folded Spill
	sd	s5, 104(sp)                     # 8-byte Folded Spill
	sd	s6, 96(sp)                      # 8-byte Folded Spill
	sd	s7, 88(sp)                      # 8-byte Folded Spill
	sd	s8, 80(sp)                      # 8-byte Folded Spill
	sd	s9, 72(sp)                      # 8-byte Folded Spill
	sd	s10, 64(sp)                     # 8-byte Folded Spill
	sd	s11, 56(sp)                     # 8-byte Folded Spill
	.cfi_offset ra, -8
	.cfi_offset s0, -16
	.cfi_offset s1, -24
	.cfi_offset s2, -32
	.cfi_offset s3, -40
	.cfi_offset s4, -48
	.cfi_offset s5, -56
	.cfi_offset s6, -64
	.cfi_offset s7, -72
	.cfi_offset s8, -80
	.cfi_offset s9, -88
	.cfi_offset s10, -96
	.cfi_offset s11, -104
	mv	s5, a6
	mv	s6, a1
	li	a0, 0
	ld	a1, 184(sp)
	sd	a1, 16(sp)                      # 8-byte Folded Spill
	li	a1, 64
	vsetvli	zero, a1, e32, m8, ta, ma
	vmv.v.i	v8, 0
.Lpcrel_hi0:
	auipc	a1, %got_pcrel_hi(Y_spad)
	ld	a1, %pcrel_lo(.Lpcrel_hi0)(a1)
	sd	a1, 48(sp)                      # 8-byte Folded Spill
.Lpcrel_hi1:
	auipc	a1, %got_pcrel_hi(W_spad)
	ld	a2, %pcrel_lo(.Lpcrel_hi1)(a1)
.Lpcrel_hi2:
	auipc	a1, %got_pcrel_hi(X_spad)
	ld	t2, %pcrel_lo(.Lpcrel_hi2)(a1)
	lui	a1, 262147
	slli	a1, a1, 2
	addi	a5, a1, 4
	lui	a1, 16384
	addiw	a1, a1, 1025
	slli	a1, a1, 22
	sd	a1, 8(sp)                       # 8-byte Folded Spill
	addi	s3, a1, 32
	li	a1, 1
	slli	a4, a1, 37
	addi	s9, a4, 1
	mv	a4, a2
	slli	s0, a1, 32
	addi	s1, s0, 64
	lui	a2, 32769
	addiw	a2, a2, -2047
	slli	a2, a2, 21
	addi	a2, a2, 128
	slli	a1, a1, 39
	addi	a3, a1, 1
	lui	s4, 4
	vsetivli	zero, 8, e32, m1, ta, ma
	vmv.v.i	v16, 0
	lui	a1, 262171
	slli	a1, a1, 2
	addi	a1, a1, 4
	sd	a1, 0(sp)                       # 8-byte Folded Spill
	mv	t0, a0
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	addi	t0, t0, 64
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_5 Depth 2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	li	a1, 63
	blt	a1, t0, .LBB0_17
# %bb.3:                                #   in Loop: Header=BB0_2 Depth=1
	li	t3, 0
	li	t1, 0
	slli	s10, t0, 5
	sd	t0, 24(sp)                      # 8-byte Folded Spill
	j	.LBB0_5
.LBB0_4:                                #   in Loop: Header=BB0_5 Depth=2
	ld	t0, 24(sp)                      # 8-byte Folded Reload
	slli	a1, t0, 7
	ld	t1, 32(sp)                      # 8-byte Folded Reload
	add	a1, a1, t1
	slli	a1, a1, 2
	ld	a6, 16(sp)                      # 8-byte Folded Reload
	add	a6, a6, a1
	ld	a1, 8(sp)                       # 8-byte Folded Reload
	addi	a1, a1, 128
	mv	a7, a4
	ld	a4, 0(sp)                       # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 0, zero, a1, a4
	#NO_APP
	mv	a4, a7
	#APP
	.insn r 43, 3, 4, zero, a0, a3
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, s1
	#NO_APP
	ld	a1, 48(sp)                      # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 3, zero, a6, a1
	#NO_APP
	addi	t1, t1, 128
	ld	t3, 40(sp)                      # 8-byte Folded Reload
	addi	t3, t3, 512
.LBB0_5:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Loop Header: Depth=2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	li	a1, 127
	blt	a1, t1, .LBB0_1
# %bb.6:                                #   in Loop: Header=BB0_5 Depth=2
	sd	t1, 32(sp)                      # 8-byte Folded Spill
	li	s11, 0
	li	a1, 64
	vsetvli	zero, a1, e32, m8, ta, ma
	ld	a1, 48(sp)                      # 8-byte Folded Reload
	vse32.v	v8, (a1)
	sd	t3, 40(sp)                      # 8-byte Folded Spill
	j	.LBB0_8
.LBB0_7:                                #   in Loop: Header=BB0_8 Depth=3
	vsetivli	zero, 8, e32, m1, ta, ma
	vle32.v	v17, (a4)
	addi	a1, a4, 32
	vle32.v	v18, (a1)
	addi	a1, a4, 64
	vle32.v	v19, (a1)
	addi	a1, a4, 96
	vle32.v	v20, (a1)
	sf.vc.iv	1, 0, v17, 0
	sf.vc.iv	1, 0, v18, 0
	sf.vc.iv	1, 0, v19, 0
	sf.vc.iv	1, 0, v20, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	vle32.v	v17, (t2)
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	0, 0, v17, 0
	addi	a1, t2, 32
	vle32.v	v17, (a1)
	addi	a1, t2, 64
	vle32.v	v18, (a1)
	addi	a1, t2, 96
	vle32.v	v19, (a1)
	addi	a1, t2, 128
	vle32.v	v20, (a1)
	sf.vc.iv	0, 0, v17, 0
	sf.vc.iv	0, 0, v18, 0
	sf.vc.iv	0, 0, v19, 0
	sf.vc.iv	0, 0, v20, 0
	addi	a1, t2, 160
	vle32.v	v17, (a1)
	addi	a1, t2, 192
	vle32.v	v18, (a1)
	addi	a1, t2, 224
	vle32.v	v19, (a1)
	sf.vc.iv	0, 0, v17, 0
	sf.vc.iv	0, 0, v18, 0
	ld	t0, 48(sp)                      # 8-byte Folded Reload
	vle32.v	v17, (t0)
	sf.vc.iv	0, 0, v19, 0
	li	a1, 8
	vsetvli	zero, a1, e32, m1, ta, ma
	sf.vc.i	1, 0, 0, 4
	vsetivli	zero, 8, e32, m1, ta, ma
	sf.vc.v.i	2, 0, v18, 0
	vfadd.vv	v17, v17, v18
	addi	a6, t0, 32
	vle32.v	v18, (a6)
	sf.vc.v.i	2, 0, v19, 0
	addi	a7, t0, 64
	vle32.v	v20, (a7)
	vfadd.vv	v18, v18, v19
	vse32.v	v18, (a6)
	sf.vc.v.i	2, 0, v18, 0
	vfadd.vv	v18, v20, v18
	vse32.v	v18, (a7)
	addi	a6, t0, 96
	vle32.v	v18, (a6)
	sf.vc.v.i	2, 0, v19, 0
	addi	a7, t0, 128
	vle32.v	v20, (a7)
	vfadd.vv	v18, v18, v19
	vse32.v	v18, (a6)
	sf.vc.v.i	2, 0, v18, 0
	vfadd.vv	v18, v20, v18
	vse32.v	v18, (a7)
	addi	a7, t0, 160
	vle32.v	v18, (a7)
	sf.vc.v.i	2, 0, v19, 0
	addi	a6, t0, 192
	vle32.v	v20, (a6)
	vfadd.vv	v18, v18, v19
	vse32.v	v18, (a7)
	sf.vc.v.i	2, 0, v18, 0
	vfadd.vv	v18, v20, v18
	addi	a7, t0, 224
	vle32.v	v19, (a7)
	vse32.v	v18, (a6)
	vse32.v	v17, (t0)
	sf.vc.v.i	2, 0, v17, 0
	vfadd.vv	v17, v19, v17
	vse32.v	v17, (a7)
	addi	s11, s11, 32
	add	t3, t3, s4
.LBB0_8:                                #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        # =>    This Loop Header: Depth=3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	li	a1, 31
	blt	a1, s11, .LBB0_4
# %bb.9:                                #   in Loop: Header=BB0_8 Depth=3
	li	t1, 0
	j	.LBB0_11
.LBB0_10:                               #   in Loop: Header=BB0_11 Depth=4
	addi	t1, t1, 1
.LBB0_11:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        # =>      This Loop Header: Depth=4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	blt	a0, t1, .LBB0_7
# %bb.12:                               #   in Loop: Header=BB0_11 Depth=4
	li	t0, 0
	slli	a7, t1, 11
	slli	s2, t1, 8
	add	s2, s2, t2
	mv	t4, a4
	mv	s8, t3
	j	.LBB0_14
.LBB0_13:                               #   in Loop: Header=BB0_14 Depth=5
	addi	t0, t0, 1
	add	s8, s8, s4
	addi	t4, t4, 128
.LBB0_14:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        # =>        This Loop Header: Depth=5
                                        #             Child Loop BB0_16 Depth 6
	blt	a0, t0, .LBB0_10
# %bb.15:                               #   in Loop: Header=BB0_14 Depth=5
	li	s7, 0
	slli	a1, t0, 5
	add	t6, a7, a1
	add	a1, s10, s11
	add	a1, a1, t6
	slli	a1, a1, 2
	add	a1, a1, s6
	mv	t6, t4
	mv	ra, s8
	bltz	a0, .LBB0_13
.LBB0_16:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        #           Parent Loop BB0_14 Depth=5
                                        # =>          This Inner Loop Header: Depth=6
	#APP
	.insn r 43, 3, 0, zero, s3, a5
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, s9
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, s1
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a1, s2
	#NO_APP
	add	a6, ra, s5
	#APP
	.insn r 43, 3, 0, zero, a2, a5
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, a3
	#NO_APP
	addi	t5, s0, 32
	#APP
	.insn r 43, 3, 5, zero, a0, t5
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a6, t6
	#NO_APP
	addi	s7, s7, 1
	addi	ra, ra, 512
	addi	t6, t6, 128
	bge	a0, s7, .LBB0_16
	j	.LBB0_13
.LBB0_17:
	ld	ra, 152(sp)                     # 8-byte Folded Reload
	ld	s0, 144(sp)                     # 8-byte Folded Reload
	ld	s1, 136(sp)                     # 8-byte Folded Reload
	ld	s2, 128(sp)                     # 8-byte Folded Reload
	ld	s3, 120(sp)                     # 8-byte Folded Reload
	ld	s4, 112(sp)                     # 8-byte Folded Reload
	ld	s5, 104(sp)                     # 8-byte Folded Reload
	ld	s6, 96(sp)                      # 8-byte Folded Reload
	ld	s7, 88(sp)                      # 8-byte Folded Reload
	ld	s8, 80(sp)                      # 8-byte Folded Reload
	ld	s9, 72(sp)                      # 8-byte Folded Reload
	ld	s10, 64(sp)                     # 8-byte Folded Reload
	ld	s11, 56(sp)                     # 8-byte Folded Reload
	addi	sp, sp, 160
	ret
.Lfunc_end0:
	.size	kernel, .Lfunc_end0-kernel
	.cfi_endproc
	.section	.stack_sizes,"o",@progbits,.text
	.quad	.Lfunc_begin0
	.ascii	"\240\001"
	.text
                                        # -- End function
	.globl	wrapper_kernel                  # -- Begin function wrapper_kernel
	.p2align	1
	.type	wrapper_kernel,@function
wrapper_kernel:                         # @wrapper_kernel
.Lfunc_begin1:
	.cfi_startproc
# %bb.0:
	addi	sp, sp, -64
	.cfi_def_cfa_offset 64
	sd	ra, 56(sp)                      # 8-byte Folded Spill
	.cfi_offset ra, -8
	addi	t0, sp, 88
	vsetivli	zero, 4, e64, m1, ta, ma
	vle64.v	v8, (t0)
	addi	t0, sp, 64
	vsetivli	zero, 2, e64, m1, ta, ma
	vle64.v	v9, (t0)
	ld	t0, 80(sp)
	sd	t0, 16(sp)
	vse64.v	v9, (sp)
	addi	t0, sp, 24
	vsetivli	zero, 4, e64, m1, ta, ma
	vse64.v	v8, (t0)
	call	kernel
	ld	ra, 56(sp)                      # 8-byte Folded Reload
	addi	sp, sp, 64
	ret
.Lfunc_end1:
	.size	wrapper_kernel, .Lfunc_end1-wrapper_kernel
	.cfi_endproc
	.section	.stack_sizes,"o",@progbits,.text
	.quad	.Lfunc_begin1
	.byte	64
	.text
                                        # -- End function
	.section	".note.GNU-stack","",@progbits
