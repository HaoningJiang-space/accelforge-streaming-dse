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
	mv	t3, a6
	mv	s6, a1
	li	a0, 0
	ld	a1, 184(sp)
	sd	a1, 24(sp)                      # 8-byte Folded Spill
.Lpcrel_hi0:
	auipc	a1, %got_pcrel_hi(Y_spad)
	ld	t4, %pcrel_lo(.Lpcrel_hi0)(a1)
	vsetivli	zero, 16, e32, m2, ta, ma
	vmv.v.i	v8, 0
.Lpcrel_hi1:
	auipc	a1, %got_pcrel_hi(X_spad)
	ld	t1, %pcrel_lo(.Lpcrel_hi1)(a1)
	lui	a1, 262147
	slli	a1, a1, 2
	addi	a2, a1, 4
	lui	a1, 65537
	addiw	a1, a1, 1
	slli	a1, a1, 20
	sd	a1, 16(sp)                      # 8-byte Folded Spill
	addi	s2, a1, 8
	li	a1, 1
	slli	a5, a1, 37
	addi	s4, a5, 1
	slli	a3, a1, 32
	addi	a4, a3, 16
.Lpcrel_hi2:
	auipc	s1, %got_pcrel_hi(W_spad)
	ld	t2, %pcrel_lo(.Lpcrel_hi2)(s1)
	lui	s1, 131074
	addiw	s1, s1, 1
	slli	s1, s1, 19
	addi	s0, s1, 32
	slli	a1, a1, 39
	addi	s1, a1, 1
	addi	a3, a3, 8
	lui	s3, 1
	vsetivli	zero, 8, e32, m1, ta, ma
	vmv.v.i	v10, 0
	li	a5, 8
	lui	a1, 262171
	slli	a1, a1, 2
	addi	a1, a1, 4
	sd	a1, 8(sp)                       # 8-byte Folded Spill
	mv	a7, a0
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	addi	a7, a7, 16
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_5 Depth 2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	li	a1, 63
	blt	a1, a7, .LBB0_17
# %bb.3:                                #   in Loop: Header=BB0_2 Depth=1
	li	s8, 0
	li	t0, 0
	slli	s9, a7, 5
	sd	a7, 32(sp)                      # 8-byte Folded Spill
	j	.LBB0_5
.LBB0_4:                                #   in Loop: Header=BB0_5 Depth=2
	ld	a7, 32(sp)                      # 8-byte Folded Reload
	slli	a1, a7, 7
	ld	t0, 40(sp)                      # 8-byte Folded Reload
	add	a1, a1, t0
	slli	a1, a1, 2
	ld	a6, 24(sp)                      # 8-byte Folded Reload
	add	a6, a6, a1
	ld	a1, 16(sp)                      # 8-byte Folded Reload
	addi	a1, a1, 32
	ld	a5, 8(sp)                       # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 0, zero, a1, a5
	#NO_APP
	li	a5, 8
	#APP
	.insn r 43, 3, 4, zero, a0, s1
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, a4
	#NO_APP
	#APP
	.insn r 43, 3, 3, zero, a6, t4
	#NO_APP
	addi	t0, t0, 32
	ld	s8, 48(sp)                      # 8-byte Folded Reload
	addi	s8, s8, 128
.LBB0_5:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Loop Header: Depth=2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	li	a1, 127
	blt	a1, t0, .LBB0_1
# %bb.6:                                #   in Loop: Header=BB0_5 Depth=2
	sd	t0, 40(sp)                      # 8-byte Folded Spill
	li	s10, 0
	vsetivli	zero, 16, e32, m2, ta, ma
	vse32.v	v8, (t4)
	sd	s8, 48(sp)                      # 8-byte Folded Spill
	j	.LBB0_8
.LBB0_7:                                #   in Loop: Header=BB0_8 Depth=3
	vsetivli	zero, 8, e32, m1, ta, ma
	vle32.v	v11, (t2)
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	vle32.v	v11, (t1)
	addi	a1, t1, 32
	vle32.v	v12, (a1)
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	1, 0, v10, 0
	sf.vc.iv	0, 0, v11, 0
	sf.vc.iv	0, 0, v12, 0
	vsetvli	zero, a5, e32, m1, ta, ma
	sf.vc.i	1, 0, 0, 4
	vsetivli	zero, 8, e32, m1, ta, ma
	vle32.v	v11, (t4)
	sf.vc.v.i	2, 0, v12, 0
	addi	a1, t4, 32
	vle32.v	v13, (a1)
	vfadd.vv	v11, v11, v12
	vse32.v	v11, (t4)
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v11, v13, v11
	vse32.v	v11, (a1)
	addi	s10, s10, 8
	add	s8, s8, s3
.LBB0_8:                                #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        # =>    This Loop Header: Depth=3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	li	a1, 31
	blt	a1, s10, .LBB0_4
# %bb.9:                                #   in Loop: Header=BB0_8 Depth=3
	li	t0, 0
	j	.LBB0_11
.LBB0_10:                               #   in Loop: Header=BB0_11 Depth=4
	addi	t0, t0, 1
.LBB0_11:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        # =>      This Loop Header: Depth=4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	blt	a0, t0, .LBB0_7
# %bb.12:                               #   in Loop: Header=BB0_11 Depth=4
	li	a7, 0
	slli	ra, t0, 9
	slli	t5, t0, 6
	add	t5, t5, t1
	mv	s7, s8
	j	.LBB0_14
.LBB0_13:                               #   in Loop: Header=BB0_14 Depth=5
	addi	a7, a7, 1
	add	s7, s7, s3
.LBB0_14:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        # =>        This Loop Header: Depth=5
                                        #             Child Loop BB0_16 Depth 6
	blt	a0, a7, .LBB0_10
# %bb.15:                               #   in Loop: Header=BB0_14 Depth=5
	li	s5, 0
	slli	a1, a7, 3
	add	t6, ra, a1
	add	a1, s9, s10
	add	a1, a1, t6
	slli	a1, a1, 2
	add	a1, a1, s6
	slli	t6, a7, 5
	add	t6, t6, t2
	mv	s11, s7
	bltz	a0, .LBB0_13
.LBB0_16:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        #           Parent Loop BB0_14 Depth=5
                                        # =>          This Inner Loop Header: Depth=6
	#APP
	.insn r 43, 3, 0, zero, s2, a2
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, s4
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, a4
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a1, t5
	#NO_APP
	add	a6, s11, t3
	#APP
	.insn r 43, 3, 0, zero, s0, a2
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, s1
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, a3
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a6, t6
	#NO_APP
	addi	s5, s5, 1
	addi	s11, s11, 128
	bge	a0, s5, .LBB0_16
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
