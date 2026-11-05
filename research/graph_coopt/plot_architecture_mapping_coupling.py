"""Summarize and plot independently validated RQ1 coupling grids."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
import numpy as np


def summarize(reports):
    cases = []
    for label, r in reports:
        if r['status'] != 'complete':
            raise ValueError(f'incomplete grid: {label}')
        budgets = r['budget_comparisons']
        fixed = [b['fixed_nominal_shape']['relative_edp_gap'] for b in budgets]
        frozen = [b['fixed_anchor_mapping']['relative_edp_gap'] for b in budgets
                  if b['fixed_anchor_mapping']['feasible']]
        controls = [c['relative_gap_to_full_graph_search'] for c in r['zero_fused_loop_controls']]
        cases.append(dict(
            label=label, case=r['case'], independent_searches=len(r['records']),
            control_searches=len(controls), budget_strata=len(budgets),
            distinct_grid_winning_shapes=sorted({b['reference_best_key'].split('_')[0] for b in budgets}),
            fixed_16x16_median_edp_gap=float(np.median(fixed)),
            fixed_16x16_max_edp_gap=max(fixed),
            frozen_anchor_feasible_strata=len(frozen),
            frozen_anchor_infeasible_strata=len(budgets) - len(frozen),
            frozen_anchor_max_feasible_edp_gap=max(frozen) if frozen else None,
            adjacent_mapping_comparisons=len(r['mapping_switches']),
            adjacent_disjoint_complete_tied_mapping_sets=sum(c['complete_tied_sets_disjoint'] is True
                                                            for c in r['mapping_switches']),
            adjacent_storage_component_set_changes=sum(c['intermediate_storage_components_changed']
                                                       for c in r['mapping_switches']),
            zero_fused_loop_control_max_edp_gap=max(controls) if controls else None,
            legal_transfer_points_better_than_grid_reference=sum(b['best_known_edp'] < b['reference_edp'] * (1 - 1e-6)
                                                                for b in budgets),
            search_rows_generated=sum(p['search_stats']['rows_generated'] for p in r['records']),
            diagnostic_search_seconds=sum(p['spec_search_and_selection_s'] for p in r['records']),
        ))
    return dict(scope='RQ1 model-level coupling; fixed resource strata, not a new joint optimizer or a performance benchmark.',
                cases=cases, calibrated_area_budget=False,
                exhaustive_architecture_by_complete_mapping_equals_joint_optimum_mathematically=True,
                ffm_grid_is_a_global_optimality_oracle=False,
                independent_selected_mapping_validations=sum(c['independent_searches'] for c in cases),
                control_selected_mapping_validations=sum(c['control_searches'] for c in cases),
                known_limitations=['Fixed NVDLA hierarchy, unit action energies, clock and zero leakage.',
                                   'GB bandwidth scales action latency only; port area/energy is not calibrated.',
                                   'Equal PE counts do not establish equal physical area or clock.',
                                   'Fixed/tied returned-frontier comparisons do not prove complete Mapspace optimality.',
                                   'Zero fused loops is not the same as all intermediates stored in DRAM.'])


def plot(reports, output):
    fig, axes = plt.subplots(2, len(reports), figsize=(4.3 * len(reports), 6.4), squeeze=False,
                             layout='constrained')
    values = [100 * b['fixed_nominal_shape']['relative_edp_gap']
              for _, r in reports for b in r['budget_comparisons']]
    controls = [100 * c['relative_gap_to_full_graph_search']
                for _, r in reports for c in r['zero_fused_loop_controls']]
    norms = [Normalize(min(0., min(values)), max(1., max(values))),
             Normalize(min(0., min(controls)), max(1., max(controls)))]
    for column, (label, r) in enumerate(reports):
        caps = sorted(r['config']['capacities_bytes'])
        scales = sorted(r['config']['gb_latency_scales'])
        rows = {b['budget']['globalbuffer_bytes']: {} for b in r['budget_comparisons']}
        for b in r['budget_comparisons']:
            rows[b['budget']['globalbuffer_bytes']][b['budget']['gb_latency_scale']] = b
        controlled = {(c['point']['capacity_bytes'], c['point']['gb_latency_scale']): c
                      for c in r['zero_fused_loop_controls']}
        for panel in range(2):
            ax = axes[panel, column]
            data = np.array([[100 * (rows[cap][scale]['fixed_nominal_shape']['relative_edp_gap'] if panel == 0 else
                                    controlled[(cap, scale)]['relative_gap_to_full_graph_search'])
                              for scale in scales] for cap in caps])
            im = ax.imshow(data, norm=norms[panel], cmap='YlOrRd', aspect='auto')
            for i, cap in enumerate(caps):
                for j, scale in enumerate(scales):
                    prefix = rows[cap][scale]['reference_best_key'].split('_')[0].replace('x', '×') + '\n' if panel == 0 else ''
                    color = 'white' if norms[panel](data[i, j]) > .65 else '#202124'
                    ax.text(j, i, f'{prefix}{data[i,j]:+.1f}%', ha='center', va='center', color=color, fontsize=10)
            ax.set_xticks(range(len(scales)), [f'{512/s:g}/{128/s:g}' for s in scales])
            ax.set_yticks(range(len(caps)), [f'{c/1024:g}' for c in caps])
            ax.set_xlabel('GB read/write bandwidth (GB/s)')
            ax.set_ylabel('GlobalBuffer capacity (KiB)')
            ax.set_title(f'{label}: ' + ('fixed 16×16 EDP penalty\ncell label: grid-winning shape' if panel == 0 else
                                         'zero-fused-loop EDP penalty\nat the same 16×16 shape'), fontsize=11)
            if column == len(reports) - 1:
                fig.colorbar(im, ax=axes[panel, :].tolist(), label='EDP gap (%)', shrink=.8)
    fig.suptitle('Architecture–mapping coupling under equal resource budgets\n'
                 'NVDLA cost model, 256 PEs; each cell compares the same SRAM and bandwidth', fontsize=13)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output.with_suffix('.png'), dpi=180)
    fig.savefig(output.with_suffix('.pdf'))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    args = parser.parse_args()
    reports = [(label, json.loads((args.directory / f'{label}.json').read_text())) for label in ('2mm', '3mm', 'glu')]
    summary = summarize(reports)
    (args.directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    plot(reports, args.directory / 'coupling')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
