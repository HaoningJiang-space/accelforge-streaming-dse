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
	addi	sp, sp, -176
	.cfi_def_cfa_offset 176
	sd	ra, 168(sp)                     # 8-byte Folded Spill
	sd	s0, 160(sp)                     # 8-byte Folded Spill
	sd	s1, 152(sp)                     # 8-byte Folded Spill
	sd	s2, 144(sp)                     # 8-byte Folded Spill
	sd	s3, 136(sp)                     # 8-byte Folded Spill
	sd	s4, 128(sp)                     # 8-byte Folded Spill
	sd	s5, 120(sp)                     # 8-byte Folded Spill
	sd	s6, 112(sp)                     # 8-byte Folded Spill
	sd	s7, 104(sp)                     # 8-byte Folded Spill
	sd	s8, 96(sp)                      # 8-byte Folded Spill
	sd	s9, 88(sp)                      # 8-byte Folded Spill
	sd	s10, 80(sp)                     # 8-byte Folded Spill
	sd	s11, 72(sp)                     # 8-byte Folded Spill
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
	mv	s10, a1
	li	a0, 0
	ld	a1, 200(sp)
	sd	a1, 24(sp)                      # 8-byte Folded Spill
.Lpcrel_hi0:
	auipc	a1, %got_pcrel_hi(Y_spad)
	ld	a1, %pcrel_lo(.Lpcrel_hi0)(a1)
	sd	a1, 56(sp)                      # 8-byte Folded Spill
	vsetivli	zero, 16, e32, m2, ta, ma
	vmv.v.i	v8, 0
	li	t5, 1
.Lpcrel_hi1:
	auipc	a1, %got_pcrel_hi(X_spad)
	ld	t2, %pcrel_lo(.Lpcrel_hi1)(a1)
	lui	a1, 262147
	slli	a1, a1, 2
	addi	a3, a1, 4
	lui	a1, 65537
	addiw	a1, a1, 1
	slli	a1, a1, 20
	sd	a1, 16(sp)                      # 8-byte Folded Spill
	addi	s3, a1, 128
	slli	a4, t5, 40
	addi	t4, a4, 1
	slli	a1, t5, 32
	addi	a2, a1, 16
.Lpcrel_hi2:
	auipc	a5, %got_pcrel_hi(W_spad)
	ld	s6, %pcrel_lo(.Lpcrel_hi2)(a5)
	lui	a5, 8192
	addiw	a5, a5, 513
	slli	a5, a5, 23
	addi	s1, a5, 32
	slli	s0, t5, 37
	addi	s0, s0, 1
	addi	a5, a1, 256
	lui	s4, 4
	vsetivli	zero, 8, e32, m1, ta, ma
	vid.v	v10
	vmv.v.i	v11, 0
	lui	a1, 262171
	slli	a1, a1, 2
	addi	a1, a1, 4
	sd	a1, 8(sp)                       # 8-byte Folded Spill
	mv	t0, a0
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	addi	t0, t0, 16
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_5 Depth 2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_18 Depth 4
	li	a1, 15
	blt	a1, t0, .LBB0_19
# %bb.3:                                #   in Loop: Header=BB0_2 Depth=1
	sd	zero, 48(sp)                    # 8-byte Folded Spill
	li	t1, 0
	slli	s11, t0, 8
	sd	t0, 32(sp)                      # 8-byte Folded Spill
	j	.LBB0_5
.LBB0_4:                                #   in Loop: Header=BB0_5 Depth=2
	ld	t0, 32(sp)                      # 8-byte Folded Reload
	slli	a1, t0, 5
	ld	t1, 40(sp)                      # 8-byte Folded Reload
	add	a1, a1, t1
	slli	a1, a1, 2
	ld	a6, 24(sp)                      # 8-byte Folded Reload
	add	a6, a6, a1
	ld	a1, 16(sp)                      # 8-byte Folded Reload
	addi	a1, a1, 32
	ld	a4, 8(sp)                       # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 0, zero, a1, a4
	#NO_APP
	ld	a7, 56(sp)                      # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 4, zero, a0, s0
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, a2
	#NO_APP
	#APP
	.insn r 43, 3, 3, zero, a6, a7
	#NO_APP
	addi	t1, t1, 32
	ld	a1, 48(sp)                      # 8-byte Folded Reload
	addi	a1, a1, 128
	sd	a1, 48(sp)                      # 8-byte Folded Spill
.LBB0_5:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Loop Header: Depth=2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_18 Depth 4
	li	a1, 31
	blt	a1, t1, .LBB0_1
# %bb.6:                                #   in Loop: Header=BB0_5 Depth=2
	sd	t1, 40(sp)                      # 8-byte Folded Spill
	li	ra, 0
	vsetivli	zero, 16, e32, m2, ta, ma
	ld	a1, 56(sp)                      # 8-byte Folded Reload
	vse32.v	v8, (a1)
	ld	a1, 48(sp)                      # 8-byte Folded Reload
	sd	a1, 64(sp)                      # 8-byte Folded Spill
	j	.LBB0_8
.LBB0_7:                                #   in Loop: Header=BB0_8 Depth=3
	addi	ra, ra, 256
	lui	a1, 8
	ld	a4, 64(sp)                      # 8-byte Folded Reload
	add	a4, a4, a1
	sd	a4, 64(sp)                      # 8-byte Folded Spill
.LBB0_8:                                #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        # =>    This Loop Header: Depth=3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_18 Depth 4
	li	a1, 255
	blt	a1, ra, .LBB0_4
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
	blt	a0, t0, .LBB0_17
# %bb.12:                               #   in Loop: Header=BB0_11 Depth=4
	li	t1, 0
	slli	t3, t0, 4
	slli	s7, t0, 12
	ld	a7, 64(sp)                      # 8-byte Folded Reload
	j	.LBB0_14
.LBB0_13:                               #   in Loop: Header=BB0_14 Depth=5
	addi	t1, t1, 1
	add	a7, a7, s4
.LBB0_14:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        # =>        This Loop Header: Depth=5
                                        #             Child Loop BB0_16 Depth 6
	blt	t5, t1, .LBB0_10
# %bb.15:                               #   in Loop: Header=BB0_14 Depth=5
	li	s8, 0
	slli	a1, t1, 4
	add	t6, t3, a1
	slli	a1, t1, 7
	add	s2, s7, a1
	add	a1, s11, ra
	add	a1, a1, s2
	slli	a1, a1, 2
	add	a1, a1, s10
	slli	t6, t6, 2
	add	t6, t6, t2
	slli	s2, t1, 9
	add	s2, s2, s6
	mv	s9, a7
	bltz	a0, .LBB0_13
.LBB0_16:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        #           Parent Loop BB0_14 Depth=5
                                        # =>          This Inner Loop Header: Depth=6
	#APP
	.insn r 43, 3, 0, zero, s3, a3
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, t4
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, a2
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a1, t6
	#NO_APP
	add	a6, s9, s5
	#APP
	.insn r 43, 3, 0, zero, s1, a3
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, s0
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, a5
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a6, s2
	#NO_APP
	addi	s8, s8, 1
	addi	s9, s9, 128
	bge	a0, s8, .LBB0_16
	j	.LBB0_13
.LBB0_17:                               #   in Loop: Header=BB0_8 Depth=3
	li	t0, 0
	addi	t1, s6, 480
	li	t3, 248
	mv	s7, t2
	bltz	t5, .LBB0_7
.LBB0_18:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        # =>      This Inner Loop Header: Depth=4
	addi	a1, t1, -480
	vsetivli	zero, 8, e32, m1, ta, mu
	vle32.v	v12, (a1)
	addi	a1, t1, -448
	vle32.v	v13, (a1)
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	addi	a1, t1, -416
	vle32.v	v12, (a1)
	addi	a1, t1, -384
	vle32.v	v13, (a1)
	addi	a1, t1, -352
	vle32.v	v14, (a1)
	addi	a1, t1, -320
	vle32.v	v15, (a1)
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	sf.vc.iv	1, 0, v14, 0
	sf.vc.iv	1, 0, v15, 0
	addi	a1, t1, -288
	vle32.v	v12, (a1)
	addi	a1, t1, -256
	vle32.v	v13, (a1)
	addi	a1, t1, -224
	vle32.v	v14, (a1)
	addi	a1, t1, -192
	vle32.v	v15, (a1)
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	sf.vc.iv	1, 0, v14, 0
	sf.vc.iv	1, 0, v15, 0
	addi	a1, t1, -160
	vle32.v	v12, (a1)
	addi	a1, t1, -128
	vle32.v	v13, (a1)
	addi	a1, t1, -96
	vle32.v	v14, (a1)
	addi	a1, t1, -64
	vle32.v	v15, (a1)
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	sf.vc.iv	1, 0, v14, 0
	sf.vc.iv	1, 0, v15, 0
	addi	a1, t1, -32
	vle32.v	v12, (a1)
	addi	a1, t3, 8
	vmslt.vx	v0, v10, a1
	vle32.v	v13, (t1)
	vmv1r.v	v14, v11
	vle32.v	v14, (s7), v0.t
	vmslt.vx	v0, v10, t3
	addi	a1, s7, 32
	vmv1r.v	v15, v11
	vle32.v	v15, (a1), v0.t
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	sf.vc.iv	0, 0, v14, 0
	sf.vc.iv	0, 0, v15, 0
	li	a1, 8
	vsetvli	zero, a1, e32, m1, ta, ma
	sf.vc.i	1, 0, 0, 4
	vsetivli	zero, 8, e32, m1, ta, ma
	ld	a4, 56(sp)                      # 8-byte Folded Reload
	vle32.v	v12, (a4)
	sf.vc.v.i	2, 0, v13, 0
	addi	a1, a4, 32
	vle32.v	v14, (a1)
	vfadd.vv	v12, v12, v13
	vse32.v	v12, (a4)
	sf.vc.v.i	2, 0, v12, 0
	vfadd.vv	v12, v14, v12
	vse32.v	v12, (a1)
	addi	t0, t0, 1
	addi	s7, s7, 64
	addi	t3, t3, -16
	addi	t1, t1, 512
	bge	t5, t0, .LBB0_18
	j	.LBB0_7
.LBB0_19:
	ld	ra, 168(sp)                     # 8-byte Folded Reload
	ld	s0, 160(sp)                     # 8-byte Folded Reload
	ld	s1, 152(sp)                     # 8-byte Folded Reload
	ld	s2, 144(sp)                     # 8-byte Folded Reload
	ld	s3, 136(sp)                     # 8-byte Folded Reload
	ld	s4, 128(sp)                     # 8-byte Folded Reload
	ld	s5, 120(sp)                     # 8-byte Folded Reload
	ld	s6, 112(sp)                     # 8-byte Folded Reload
	ld	s7, 104(sp)                     # 8-byte Folded Reload
	ld	s8, 96(sp)                      # 8-byte Folded Reload
	ld	s9, 88(sp)                      # 8-byte Folded Reload
	ld	s10, 80(sp)                     # 8-byte Folded Reload
	ld	s11, 72(sp)                     # 8-byte Folded Reload
	addi	sp, sp, 176
	ret
.Lfunc_end0:
	.size	kernel, .Lfunc_end0-kernel
	.cfi_endproc
	.section	.stack_sizes,"o",@progbits,.text
	.quad	.Lfunc_begin0
	.ascii	"\260\001"
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
