set -eu
base=/project/haoning/graph_separation_2047138b
trap 'rc=$?; echo "$rc" > "$base/exitcode"' EXIT
cd "$base/source"
export PYTHONHASHSEED=0
python3 - <<'PY' > "$base/environment.json"
import json,platform,os,socket,subprocess
print(json.dumps(dict(host=socket.gethostname(),python=platform.python_version(),platform=platform.platform(),
 affinity=sorted(os.sched_getaffinity(0)),hash_seed=os.environ['PYTHONHASHSEED'],
 revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()),indent=2))
PY
python3 -m unittest research.dag_mapping.test_conditional_separation research.dag_mapping.test_hierarchy research.index_coupling.test_prefix_reductions > "$base/tests.txt" 2>&1
mkdir "$base/results"
for case in two_stage_join asymmetric_join mixed_join; do
 timeout 300s python3 -m research.dag_mapping.conditional_separation --case "$case" --out "$base/results/$case"
done
