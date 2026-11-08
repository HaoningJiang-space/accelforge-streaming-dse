# Two-level SRAM and mixed-phase hardware gate

The gate tests one prefill projection and one single-query decode score
contraction. It uses 8-bit tensors and 2,048 MACs at 1 GHz. The two SRAM levels
hold shared data and stripe-private weights, respectively. The experiment
varies the PE geometry, global bank count, global capacity per bank, and
private capacity per stripe.

The [pinned CACTI run](https://github.com/HaoningJiang-space/accelforge-streaming-dse/actions/runs/42453899987)
characterizes 45 nm scratchpads with one dedicated read port and one dedicated
write port. The [macro table](results/sram_45nm.json) records area, dynamic
read and write energy, standby leakage, and access and cycle time. A stripe
has one private macro. The shared SRAM is built from separate global macros.
The budget covers these SRAMs. MAC and register counts are fixed, and
interconnect layout area is outside the model.

Native bit counts are prorated against 64-bit private and 512-bit global
transactions. The initial service model assumes evenly distributed global
bank traffic and rounds each bank's access and cycle times up to whole
1 GHz cycles. The one-bank sensitivity keeps all SRAM area and leakage
and limits the global service rate to one bank. Both modes use aggregate
service rates. Address-level bank calendars are outside this model.

The mapper generates native tile rows independently at each hardware point.
The EDP calculation adds the energy and time of both phases before
multiplying. The independent-hardware relaxation combines the full energy and
time fronts of both phases across the same area-capped hardware points.
Both architecture-first controls retain all ties and remap both phases
with the physical costs. One uses a fixed-price, zero-leakage proxy to choose
hardware. The other chooses hardware using only the prefill phase.

## Cold decode

The 512-token cold scan covered 15 hardware points across three area caps.
At 16, 64, and 256 decode steps, the shared-hardware penalties were 1.37%,
1.83%, and 2.00% at each cap. Prefill-first followed by full remapping tied
the shared optimum in all nine cases. The nine shared EDP values reproduced
exactly on Windows with the same CACTI table.
[Linux report](results/cold_512_linux.json.gz) ·
[Windows replay](results/cold_512_windows.json.gz)

## Resident decode

The 1,024-token variant allows the 64 KiB KV input to stay in GlobalBuffer
between decode steps. Each native tile reserves the whole tensor plus its
other live storage. The audit checks the bit-exact capacity and verifies
zero native DRAM reads of resident KV. An explicit DMA fill loads the full
input once after prefill. The fill occupies both endpoints and pays
DRAM read energy, SRAM write energy, and leakage during the transfer.

At the 1.3465 mm² SRAM cap, 13 hardware points are admitted and four
can keep KV resident. The 16-step shared winner uses a 32 × 64 array,
two 64 KiB global banks, and a 1 KiB private macro per stripe. It uses
1.0954 mm² of SRAM. In the all-bank model, prefill alone chooses a
16 × 128 array and four 16 KiB global banks. That hardware needs cold
decode because its GlobalBuffer has no room for both full KV and staging.

| Global service | Shared penalty at 16 steps | 64 steps | 256 steps | Prefill-first EDP ratio at 16 steps | Fixed-price remap ratio at 16 steps |
|---|---:|---:|---:|---:|---:|
| All banks | 7.39% | 4.73% | 1.94% | 5.86× | 1.00× |
| One bank | 8.12% | 4.85% | 2.68% | 3.46× | 1.00× |

The hardware-conflict threshold of 5% is met at 16 steps in both service
models. The fixed-price architecture selector also models residency and
ties the physical shared optimum in every resident case. The result
identifies a capacity threshold and shared-hardware cost. The matching
control leaves a search advantage open. The optimality scope is the
sampled native mappings.
[All-bank report](results/resident_1024_all_windows.json.gz) ·
[One-bank report](results/resident_1024_single_windows.json.gz)

The [Linux replay](https://github.com/HaoningJiang-space/accelforge-streaming-dse/actions/runs/42454657897)
regenerated the CACTI table byte for byte and reproduced all 27 shared and
independent EDP pairs and their shared winners exactly. The Linux native
scans took 39–45 seconds per service configuration.
[All-bank Linux report](results/resident_1024_all_linux.json.gz) ·
[One-bank Linux report](results/resident_1024_single_linux.json.gz)

## Run

Run these commands from the repository root in the AccelForge environment.

```sh
python -m research.physical_cost.cacti_sram /path/to/pinned/cacti /tmp/physical-cost
python -m research.physical_cost.mixed_gate /tmp/physical-cost/sram.json /tmp/cold.json
python -m research.physical_cost.mixed_gate /tmp/physical-cost/sram.json /tmp/resident.json --context 1024 --resident-kv
python -m research.physical_cost.mixed_gate /tmp/physical-cost/sram.json /tmp/single-bank.json --context 1024 --resident-kv --single-bank-service
```

On Windows, supply the corresponding Python arguments to
`research/runtime/run_windows.ps1` and use the checked-in macro table.
Raw run logs and CACTI inputs are available as a compressed workflow artifact.
