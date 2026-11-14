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
	addi	sp, sp, -224
	.cfi_def_cfa_offset 224
	sd	ra, 216(sp)                     # 8-byte Folded Spill
	sd	s0, 208(sp)                     # 8-byte Folded Spill
	sd	s1, 200(sp)                     # 8-byte Folded Spill
	sd	s2, 192(sp)                     # 8-byte Folded Spill
	sd	s3, 184(sp)                     # 8-byte Folded Spill
	sd	s4, 176(sp)                     # 8-byte Folded Spill
	sd	s5, 168(sp)                     # 8-byte Folded Spill
	sd	s6, 160(sp)                     # 8-byte Folded Spill
	sd	s7, 152(sp)                     # 8-byte Folded Spill
	sd	s8, 144(sp)                     # 8-byte Folded Spill
	sd	s9, 136(sp)                     # 8-byte Folded Spill
	sd	s10, 128(sp)                    # 8-byte Folded Spill
	sd	s11, 120(sp)                    # 8-byte Folded Spill
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
	sd	a1, 96(sp)                      # 8-byte Folded Spill
	li	s6, 0
	ld	a0, 248(sp)
	sd	a0, 48(sp)                      # 8-byte Folded Spill
	li	a1, 3
	slli	a0, a1, 10
	sd	a0, 104(sp)                     # 8-byte Folded Spill
	lui	a2, 1
.Lpcrel_hi0:
	auipc	a3, %got_pcrel_hi(Y_spad)
	ld	s8, %pcrel_lo(.Lpcrel_hi0)(a3)
	addi	a3, a2, -1080
	addi	a0, s8, 768
	sd	a0, 40(sp)                      # 8-byte Folded Spill
	li	a0, 64
	vsetvli	zero, a0, e32, m8, ta, ma
	vmv.v.i	v16, 0
	addi	a0, s8, 512
	sd	a0, 32(sp)                      # 8-byte Folded Spill
	addi	a0, s8, 256
	sd	a0, 24(sp)                      # 8-byte Folded Spill
	addiw	a0, a2, -1025
	sd	a0, 80(sp)                      # 8-byte Folded Spill
.Lpcrel_hi1:
	auipc	a2, %got_pcrel_hi(W_spad)
	ld	s7, %pcrel_lo(.Lpcrel_hi1)(a2)
.Lpcrel_hi2:
	auipc	a2, %got_pcrel_hi(X_spad)
	ld	a0, %pcrel_lo(.Lpcrel_hi2)(a2)
	sd	a0, 112(sp)                     # 8-byte Folded Spill
	lui	a2, 262147
	slli	a2, a2, 2
	addi	s4, a2, 4
	lui	a2, 8192
	addiw	a2, a2, 513
	sd	a2, 16(sp)                      # 8-byte Folded Spill
	slli	a2, a2, 13
	addi	a2, a2, 3
	slli	s11, a2, 10
	slli	a1, a1, 42
	addi	s10, a1, 1
	lui	t4, 1024
	lui	s9, 6
	vsetivli	zero, 8, e32, m1, ta, ma
	vid.v	v9
	vmv.v.i	v10, 0
	lui	a1, 262171
	slli	a1, a1, 2
	addi	a1, a1, 4
	sd	a1, 8(sp)                       # 8-byte Folded Spill
	li	a7, 256
	mv	a5, s6
	j	.LBB0_2
.LBB0_1:                                #   in Loop: Header=BB0_2 Depth=1
	addi	a5, a5, 128
.LBB0_2:                                # =>This Loop Header: Depth=1
                                        #     Child Loop BB0_5 Depth 2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_19 Depth 4
                                        #           Child Loop BB0_22 Depth 5
	li	a0, 127
	blt	a0, a5, .LBB0_25
# %bb.3:                                #   in Loop: Header=BB0_2 Depth=1
	li	a1, 0
	li	s1, 0
	ld	a0, 104(sp)                     # 8-byte Folded Reload
	mul	t3, a5, a0
	sd	a5, 56(sp)                      # 8-byte Folded Spill
	j	.LBB0_5
.LBB0_4:                                #   in Loop: Header=BB0_5 Depth=2
	ld	a5, 56(sp)                      # 8-byte Folded Reload
	slli	a0, a5, 8
	ld	s1, 64(sp)                      # 8-byte Folded Reload
	add	a0, a0, s1
	slli	a0, a0, 2
	ld	a1, 48(sp)                      # 8-byte Folded Reload
	add	a0, a0, a1
	ld	a1, 16(sp)                      # 8-byte Folded Reload
	slli	a1, a1, 23
	addi	a1, a1, 256
	ld	a2, 8(sp)                       # 8-byte Folded Reload
	#APP
	.insn r 43, 3, 0, zero, a1, a2
	#NO_APP
	addi	a4, a4, 1
	#APP
	.insn r 43, 3, 4, zero, s6, a4
	#NO_APP
	addi	a1, s5, 128
	#APP
	.insn r 43, 3, 5, zero, s6, a1
	#NO_APP
	#APP
	.insn r 43, 3, 3, zero, a0, s8
	#NO_APP
	addi	s1, s1, 256
	ld	a1, 72(sp)                      # 8-byte Folded Reload
	addi	a1, a1, 1024
.LBB0_5:                                #   Parent Loop BB0_2 Depth=1
                                        # =>  This Loop Header: Depth=2
                                        #       Child Loop BB0_8 Depth 3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_19 Depth 4
                                        #           Child Loop BB0_22 Depth 5
	li	a0, 255
	blt	a0, s1, .LBB0_1
# %bb.6:                                #   in Loop: Header=BB0_5 Depth=2
	sd	s1, 64(sp)                      # 8-byte Folded Spill
	li	s3, 0
	li	a0, 64
	vsetvli	zero, a0, e32, m8, ta, ma
	ld	a0, 40(sp)                      # 8-byte Folded Reload
	vse32.v	v16, (a0)
	ld	a0, 32(sp)                      # 8-byte Folded Reload
	vse32.v	v16, (a0)
	ld	a0, 24(sp)                      # 8-byte Folded Reload
	vse32.v	v16, (a0)
	vse32.v	v16, (s8)
	sd	a1, 72(sp)                      # 8-byte Folded Spill
	j	.LBB0_8
.LBB0_7:                                #   in Loop: Header=BB0_8 Depth=3
	ld	a0, 104(sp)                     # 8-byte Folded Reload
	add	s3, s3, a0
	lui	a0, 768
	ld	a1, 88(sp)                      # 8-byte Folded Reload
	add	a1, a1, a0
.LBB0_8:                                #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        # =>    This Loop Header: Depth=3
                                        #         Child Loop BB0_11 Depth 4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
                                        #         Child Loop BB0_19 Depth 4
                                        #           Child Loop BB0_22 Depth 5
	sd	a1, 88(sp)                      # 8-byte Folded Spill
	li	a4, 1
	slli	s5, a4, 32
	slli	a4, a4, 40
	ld	a0, 80(sp)                      # 8-byte Folded Reload
	blt	a0, s3, .LBB0_4
# %bb.9:                                #   in Loop: Header=BB0_8 Depth=3
	li	t0, 0
	j	.LBB0_11
.LBB0_10:                               #   in Loop: Header=BB0_11 Depth=4
	addi	t0, t0, 1
	mv	a3, ra
.LBB0_11:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        # =>      This Loop Header: Depth=4
                                        #           Child Loop BB0_14 Depth 5
                                        #             Child Loop BB0_16 Depth 6
	blt	s6, t0, .LBB0_17
# %bb.12:                               #   in Loop: Header=BB0_11 Depth=4
	mv	ra, a3
	li	t1, 0
	slli	t2, t0, 7
	slli	a1, t0, 17
	slli	a3, t0, 19
	sub	t5, a3, a1
	mv	t6, s7
	ld	s2, 88(sp)                      # 8-byte Folded Reload
	j	.LBB0_14
.LBB0_13:                               #   in Loop: Header=BB0_14 Depth=5
	addi	t1, t1, 1
	lui	a0, 768
	add	s2, s2, a0
	lui	a0, 3
	add	t6, t6, a0
.LBB0_14:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        # =>        This Loop Header: Depth=5
                                        #             Child Loop BB0_16 Depth 6
	blt	s6, t1, .LBB0_10
# %bb.15:                               #   in Loop: Header=BB0_14 Depth=5
	li	a3, 0
	ld	a0, 104(sp)                     # 8-byte Folded Reload
	mul	a1, t1, a0
	add	s0, t2, a1
	add	a1, a1, t5
	add	a5, t3, s3
	add	a1, a1, a5
	slli	a1, a1, 2
	ld	a5, 96(sp)                      # 8-byte Folded Reload
	add	a5, a5, a1
	slli	s0, s0, 2
	ld	a0, 112(sp)                     # 8-byte Folded Reload
	add	s0, s0, a0
	mv	a1, t6
	mv	s1, s2
	bltz	s6, .LBB0_13
.LBB0_16:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_11 Depth=4
                                        #           Parent Loop BB0_14 Depth=5
                                        # =>          This Inner Loop Header: Depth=6
	#APP
	.insn r 43, 3, 0, zero, s11, s4
	#NO_APP
	#APP
	.insn r 43, 3, 4, zero, s6, s10
	#NO_APP
	addi	a0, s5, 128
	#APP
	.insn r 43, 3, 5, zero, s6, a0
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a5, s0
	#NO_APP
	add	a0, s1, a6
	addiw	a2, t4, 67
	slli	a2, a2, 26
	addi	a2, a2, 256
	#APP
	.insn r 43, 3, 0, zero, a2, s4
	#NO_APP
	addi	a2, a4, 1
	#APP
	.insn r 43, 3, 4, zero, s6, a2
	#NO_APP
	addiw	a2, t4, 3
	slli	a2, a2, 10
	#APP
	.insn r 43, 3, 5, zero, s6, a2
	#NO_APP
	#APP
	.insn r 43, 3, 2, zero, a0, a1
	#NO_APP
	addi	a3, a3, 1
	addi	s1, s1, 1024
	add	a1, a1, s9
	bge	s6, a3, .LBB0_16
	j	.LBB0_13
.LBB0_17:                               #   in Loop: Header=BB0_8 Depth=3
	li	s2, 0
	li	t0, 0
	j	.LBB0_19
.LBB0_18:                               #   in Loop: Header=BB0_19 Depth=4
	addi	t0, t0, 1
	addi	s2, s2, 12
.LBB0_19:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        # =>      This Loop Header: Depth=4
                                        #           Child Loop BB0_22 Depth 5
	li	a0, 1
	blt	a0, t0, .LBB0_7
# %bb.20:                               #   in Loop: Header=BB0_19 Depth=4
	li	t2, 0
	li	t5, 0
	ld	a0, 112(sp)                     # 8-byte Folded Reload
	addi	t1, a0, 480
	li	t6, -1
	li	s5, 120
	j	.LBB0_22
.LBB0_21:                               #   in Loop: Header=BB0_22 Depth=5
	srli	a0, a1, 63
	add	a0, a0, a1
	srai	a0, a0, 1
	srai	a1, t5, 63
	xor	a0, a0, a1
	slli	a1, a0, 8
	add	a4, t2, a1
	addi	a2, a4, 256
	vsetivli	zero, 8, e32, m1, ta, mu
	vmslt.vx	v0, v9, a2
	add	a0, a0, s2
	slli	a0, a0, 8
	sub	a1, s5, a1
	add	a0, a0, a1
	slli	a0, a0, 2
	add	a2, s7, a0
	addi	a0, a2, -480
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.iv	1, 0, v8, 0
	addi	a0, a4, 248
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -448
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	addi	a0, a4, 240
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -416
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	addi	a0, a4, 232
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -384
	vmv1r.v	v12, v10
	vle32.v	v12, (a0), v0.t
	addi	a0, a4, 224
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -352
	vmv1r.v	v13, v10
	vle32.v	v13, (a0), v0.t
	sf.vc.iv	1, 0, v8, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	addi	a0, a4, 216
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -320
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	addi	a0, a4, 208
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -288
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	addi	a0, a4, 200
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -256
	vmv1r.v	v12, v10
	vle32.v	v12, (a0), v0.t
	addi	a0, a4, 192
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -224
	vmv1r.v	v13, v10
	vle32.v	v13, (a0), v0.t
	sf.vc.iv	1, 0, v8, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	addi	a0, a4, 184
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -192
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	addi	a0, a4, 176
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -160
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	addi	a0, a4, 168
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -128
	vmv1r.v	v12, v10
	vle32.v	v12, (a0), v0.t
	addi	a0, a4, 160
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -96
	vmv1r.v	v13, v10
	vle32.v	v13, (a0), v0.t
	sf.vc.iv	1, 0, v8, 0
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	addi	a0, a4, 152
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -64
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	addi	a0, a4, 144
	vmslt.vx	v0, v9, a0
	addi	a0, a2, -32
	vmv1r.v	v12, v10
	addi	a1, a4, 136
	vmslt.vx	v8, v9, a1
	vle32.v	v12, (a0), v0.t
	vmv1r.v	v13, v10
	vmv.v.v	v0, v8
	vle32.v	v13, (a2), v0.t
	add	a2, t2, a3
	addi	a0, a2, 56
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -480
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.iv	1, 0, v11, 0
	sf.vc.iv	1, 0, v12, 0
	sf.vc.iv	1, 0, v13, 0
	sf.vc.iv	0, 0, v8, 0
	addi	a0, a2, 48
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -448
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	addi	a0, a2, 40
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -416
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	addi	a0, a2, 32
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -384
	vmv1r.v	v12, v10
	vle32.v	v12, (a0), v0.t
	addi	a0, a2, 24
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -352
	vmv1r.v	v13, v10
	vle32.v	v13, (a0), v0.t
	sf.vc.iv	0, 0, v8, 0
	sf.vc.iv	0, 0, v11, 0
	sf.vc.iv	0, 0, v12, 0
	sf.vc.iv	0, 0, v13, 0
	addi	a0, a2, 16
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -320
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	addi	a0, a2, 8
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -288
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	vmslt.vx	v0, v9, a2
	addi	a0, t1, -256
	vmv1r.v	v12, v10
	vle32.v	v12, (a0), v0.t
	addi	a0, a2, -8
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -224
	vmv1r.v	v13, v10
	vle32.v	v13, (a0), v0.t
	sf.vc.iv	0, 0, v8, 0
	sf.vc.iv	0, 0, v11, 0
	sf.vc.iv	0, 0, v12, 0
	sf.vc.iv	0, 0, v13, 0
	addi	a0, a2, -16
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -192
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	addi	a0, a2, -24
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -160
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	addi	a0, a2, -32
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -128
	vmv1r.v	v12, v10
	vle32.v	v12, (a0), v0.t
	addi	a0, a2, -40
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -96
	vmv1r.v	v13, v10
	vle32.v	v13, (a0), v0.t
	sf.vc.iv	0, 0, v8, 0
	sf.vc.iv	0, 0, v11, 0
	sf.vc.iv	0, 0, v12, 0
	sf.vc.iv	0, 0, v13, 0
	addi	a0, a2, -48
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -64
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	addi	a0, a2, -56
	vmslt.vx	v0, v9, a0
	addi	a0, t1, -32
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	sf.vc.iv	0, 0, v8, 0
	addi	a0, a2, -64
	vmslt.vx	v0, v9, a0
	sf.vc.iv	0, 0, v11, 0
	vmv1r.v	v8, v10
	vle32.v	v8, (t1), v0.t
	slli	ra, t0, 7
	subw	a0, a7, ra
	vmslt.vx	v0, v9, a0
	slli	a0, t0, 9
	add	a0, a0, s8
	vmv1r.v	v11, v10
	vle32.v	v11, (a0), v0.t
	sf.vc.iv	0, 0, v8, 0
	li	a1, 8
	vsetvli	zero, a1, e32, m1, ta, ma
	sf.vc.i	1, 0, 0, 4
	vsetivli	zero, 8, e32, m1, ta, mu
	sf.vc.v.i	2, 0, v8, 0
	vfadd.vv	v8, v11, v8
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 8
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 16
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 24
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 32
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 40
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 48
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 56
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 64
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 72
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 80
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 88
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 96
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 104
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 112
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	a0, ra, 120
	subw	a1, a7, a0
	vmslt.vx	v0, v9, a1
	slli	a0, a0, 2
	add	a0, a0, s8
	vmv1r.v	v8, v10
	vle32.v	v8, (a0), v0.t
	sf.vc.v.i	2, 0, v11, 0
	vfadd.vv	v8, v8, v11
	vse32.v	v8, (a0), v0.t
	addi	t5, t5, 1
	addi	t1, t1, 512
	addi	t2, t2, -128
	addi	t6, t6, -1
	addi	s5, s5, 128
.LBB0_22:                               #   Parent Loop BB0_2 Depth=1
                                        #     Parent Loop BB0_5 Depth=2
                                        #       Parent Loop BB0_8 Depth=3
                                        #         Parent Loop BB0_19 Depth=4
                                        # =>        This Inner Loop Header: Depth=5
	li	a0, 23
	blt	a0, t5, .LBB0_18
# %bb.23:                               #   in Loop: Header=BB0_22 Depth=5
	mv	a1, t6
	bltz	t5, .LBB0_21
# %bb.24:                               #   in Loop: Header=BB0_22 Depth=5
	mv	a1, t5
	j	.LBB0_21
.LBB0_25:
	ld	ra, 216(sp)                     # 8-byte Folded Reload
	ld	s0, 208(sp)                     # 8-byte Folded Reload
	ld	s1, 200(sp)                     # 8-byte Folded Reload
	ld	s2, 192(sp)                     # 8-byte Folded Reload
	ld	s3, 184(sp)                     # 8-byte Folded Reload
	ld	s4, 176(sp)                     # 8-byte Folded Reload
	ld	s5, 168(sp)                     # 8-byte Folded Reload
	ld	s6, 160(sp)                     # 8-byte Folded Reload
	ld	s7, 152(sp)                     # 8-byte Folded Reload
	ld	s8, 144(sp)                     # 8-byte Folded Reload
	ld	s9, 136(sp)                     # 8-byte Folded Reload
	ld	s10, 128(sp)                    # 8-byte Folded Reload
	ld	s11, 120(sp)                    # 8-byte Folded Reload
	addi	sp, sp, 224
	ret
.Lfunc_end0:
	.size	kernel, .Lfunc_end0-kernel
	.cfi_endproc
	.section	.stack_sizes,"o",@progbits,.text
	.quad	.Lfunc_begin0
	.ascii	"\340\001"
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
