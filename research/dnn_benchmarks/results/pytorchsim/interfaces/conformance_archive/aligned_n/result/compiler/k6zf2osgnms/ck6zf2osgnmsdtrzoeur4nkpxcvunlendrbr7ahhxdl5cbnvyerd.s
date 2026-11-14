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
	mv	t1, a6
	mv	s5, a1
	li	a0, 0
	ld	a1, 184(sp)
	sd	a1, 16(sp)                      # 8-byte Folded Spill
	li	a1, 32
	vsetvli	zero, a1, e32, m4, ta, ma
	vmv.v.i	v12, 0
.Lpcrel_hi0:
	auipc	a1, %got_pcrel_hi(Y_spad)
	ld	a1, %pcrel_lo(.Lpcrel_hi0)(a1)
	sd	a1, 48(sp)                      # 8-byte Folded Spill
.Lpcrel_hi1:
	auipc	a1, %got_pcrel_hi(W_spad)
	ld	s8, %pcrel_lo(.Lpcrel_hi1)(a1)
	li	s2, 1
.Lpcrel_hi2:
	auipc	a1, %got_pcrel_hi(X_spad)
	ld	t6, %pcrel_lo(.Lpcrel_hi2)(a1)
	lui	a1, 262147
	slli	a1, a1, 2
	addi	a5, a1, 4
	lui	a1, 65537
	addiw	a1, a1, 1
	slli	a1, a1, 20
	addi	t4, a1, 16
	slli	a3, s2, 36
	addi	a3, a3, 1
	slli	s0, s2, 32
	addi	s0, s0, 16
	sd	a1, 8(sp)                       # 8-byte Folded Spill
	addi	s1, a1, 128
	slli	a2, s2, 40
	addi	a2, a2, 1
	lui	s3, 4
	vsetivli	zero, 8, e32, m1, ta, ma
	vid.v	v10
	vmv.v.i	v11, 0
	li	s4, 8
	lui	a1, 262171
	slli	a1, a1, 2
	addi	a1, a1, 4
	sd	a1, 0(sp)                       # 8-byte Folded Spill
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
                                        #         Child Loop BB0_18 Depth 4
	li	a1, 15
	blt	a1, a7, .LBB0_19
# %bb.3:                                #   in Loop: Header=BB0_2 Depth=1
	li	t2, 0
	li	t0, 0
	slli	s9, a7, 4
	sd	a7, 24(sp)                      # 8-byte Folded Spill
	j	.LBB0_5
.LBB0_4:                                #   in Loop: Header=BB0_5 Depth=2
	ld	a7, 24(sp)                      # 8-byte Folded Reload
	slli	a1, a7, 8
	ld	t0, 32(sp)                      # 8-byte Folded Reload
	add	a1, a1, t0
	slli	a1, a1, 2
	ld	a4, 16(sp)                      # 8-byte Folded Reload
	add	a6, a4, a1
	ld	a4, 8(sp)                       # 8-byte Folded Reload
	addi	a4, a4, 256
	ld	a1, 0(sp)                       # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 0, zero, a4, a1
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, a2
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, s0
	#NO_APP
	ld	a4, 48(sp)                      # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 3, zero, a6, a4
	#NO_APP
	addi	t0, t0, 256
	ld	t2, 40(sp)                      # 8-byte Folded Reload
	addi	t2, t2, 1024
.LBB0_5:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Loop Header: Depth=2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_18 Depth 4
	li	a1, 255
	blt	a1, t0, .LBB0_1
# %bb.6:                                #   in Loop: Header=BB0_5 Depth=2
	sd	t0, 32(sp)                      # 8-byte Folded Spill
	li	s10, 0
	li	a1, 32
	vsetvli	zero, a1, e32, m4, ta, ma
	ld	a1, 48(sp)                      # 8-byte Folded Reload
	vse32.v	v12, (a1)
	sd	t2, 40(sp)                      # 8-byte Folded Spill
	j	.LBB0_8
.LBB0_7:                                #   in Loop: Header=BB0_8 Depth=3
	addi	s10, s10, 16
	add	t2, t2, s3
.LBB0_8:                                #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        # =>    This Loop Header: Depth=3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_18 Depth 4
	li	a1, 15
	blt	a1, s10, .LBB0_4
# %bb.9:                                #   in Loop: Header=BB0_8 Depth=3
	li	ra, 0
	j	.LBB0_11
.LBB0_10:                               #   in Loop: Header=BB0_11 Depth=4
	addi	ra, ra, 1
.LBB0_11:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        # =>      This Loop Header: Depth=4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	blt	a0, ra, .LBB0_17
# %bb.12:                               #   in Loop: Header=BB0_11 Depth=4
	li	a7, 0
	slli	t0, ra, 8
	slli	a4, ra, 6
	add	a4, a4, t6
	mv	t5, s8
	mv	s7, t2
	j	.LBB0_14
.LBB0_13:                               #   in Loop: Header=BB0_14 Depth=5
	addi	a7, a7, 1
	add	s7, s7, s3
	addi	t5, t5, 64
.LBB0_14:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        # =>        This Loop Header: Depth=5
                                        #             Child Loop BB0_16 Depth 6
	blt	a0, a7, .LBB0_10
# %bb.15:                               #   in Loop: Header=BB0_14 Depth=5
	li	s6, 0
	slli	a1, a7, 4
	add	t3, t0, a1
	add	a1, s9, s10
	add	a1, a1, t3
	slli	a1, a1, 2
	add	a1, a1, s5
	mv	t3, t5
	mv	s11, s7
	bltz	s2, .LBB0_13
.LBB0_16:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        #           Parent Loop BB0_14 Depth=5
                                        # =>          This Inner Loop Header: Depth=6
	#APP
	.insn r 43, 3, 0, zero, t4, a5
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, a3
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, s0
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a1, a4
	#NO_APP
	add	a6, s11, t1
	#APP
	.insn r 43, 3, 0, zero, s1, a5
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, a0, a2
	#NO_APP
	#APP
	.insn r 43, 3, 5, zero, a0, s0
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a6, t3
	#NO_APP
	addi	s6, s6, 1
	addi	s11, s11, 512
	addi	t3, t3, 64
	bge	s2, s6, .LBB0_16
	j	.LBB0_13
.LBB0_17:                               #   in Loop: Header=BB0_8 Depth=3
.Lpcrel_hi3:
	auipc	a1, %got_pcrel_hi(W_spad)
	ld	ra, %pcrel_lo(.Lpcrel_hi3)(a1)
	li	a7, 0
	li	t0, 248
	ld	t3, 48(sp)                      # 8-byte Folded Reload
	bltz	s2, .LBB0_7
.LBB0_18:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        # =>      This Inner Loop Header: Depth=4
	addi	a1, t0, 8
	vsetivli	zero, 8, e32, m1, ta, mu
	vmslt.vx	v8, v10, a1
	vmv1r.v	v16, v11
	vmv.v.v	v0, v8
	vle32.v	v16, (ra), v0.t
	vmslt.vx	v9, v10, t0
	addi	a1, ra, 32
	vmv1r.v	v17, v11
	vmv.v.v	v0, v9
	vle32.v	v17, (a1), v0.t
	sf.vc.iv	1, 0, v16, 0
	sf.vc.iv	1, 0, v17, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v11, 0
	vle32.v	v16, (t6)
	addi	a1, t6, 32
	vle32.v	v17, (a1)
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	0, 0, v16, 0
	vmv1r.v	v16, v11
	vmv.v.v	v0, v8
	vle32.v	v16, (t3), v0.t
	sf.vc.iv	0, 0, v17, 0
	vsetvli	zero, s4, e32, m1, ta, ma
	sf.vc.i	1, 0, 0, 4
	vsetivli	zero, 8, e32, m1, ta, mu
	sf.vc.v.i	2, 0, v17, 0
	vfadd.vv	v16, v16, v17
	vse32.v	v16, (t3), v0.t
	addi	a1, t3, 32
	vmv1r.v	v8, v11
	vmv1r.v	v0, v9
	vle32.v	v8, (a1), v0.t
	sf.vc.v.i	2, 0, v16, 0
	vfadd.vv	v8, v8, v16
	vse32.v	v8, (a1), v0.t
	addi	a7, a7, 1
	addi	t3, t3, 64
	addi	t0, t0, -16
	addi	ra, ra, 64
	bge	s2, a7, .LBB0_18
	j	.LBB0_7
.LBB0_19:
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
