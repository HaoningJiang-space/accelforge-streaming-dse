#!/bin/bash
# Build the pinned LLVM/MLIR and then Neura. Everything stays under $D.
set -eux
D=${NEURA_ROOT:?set NEURA_ROOT}
LLVM_COMMIT=6146a88f60492b520a36f8f8f3231e15f3cc6082
NEURA_COMMIT=21f0fa1
mkdir -p $D; cd $D
pip3 install -q --target $D/pydeps pybind11==2.13.6 nanobind==2.15.0 ninja numpy pyyaml
export PYTHONPATH=$D/pydeps PATH=$D/pydeps/bin:$PATH
PY=/usr/bin/python3
ulimit -v 24000000
if [ ! -d llvm-project ]; then
  git clone -q --depth 1 --filter=blob:none --revision=$LLVM_COMMIT https://github.com/llvm/llvm-project.git || {
    git init -q llvm-project && git -C llvm-project remote add origin https://github.com/llvm/llvm-project.git &&
    git -C llvm-project fetch -q --depth 1 origin $LLVM_COMMIT && git -C llvm-project checkout -q FETCH_HEAD; }
fi
cmake -G Ninja -S llvm-project/llvm -B llvm-project/build \
  -DLLVM_ENABLE_PROJECTS="mlir;clang" -DLLVM_BUILD_EXAMPLES=OFF -DLLVM_TARGETS_TO_BUILD="Native" \
  -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DCMAKE_CXX_STANDARD=17 \
  -DCMAKE_CXX_FLAGS="-std=c++17 -frtti" -DMLIR_INSTALL_AGGREGATE_OBJECTS=ON -DLLVM_ENABLE_RTTI=ON \
  -DMLIR_ENABLE_BINDINGS_PYTHON=ON -DMLIR_BINDINGS_PYTHON_NB_DOMAIN=mlir \
  -DPython3_EXECUTABLE=$PY -DPython_EXECUTABLE=$PY \
  -DLLVM_PARALLEL_COMPILE_JOBS=8 -DLLVM_PARALLEL_LINK_JOBS=2
cmake --build llvm-project/build
[ -d neura ] || git clone -q https://github.com/coredac/neura.git neura
git -C neura checkout -q $NEURA_COMMIT
git -C neura submodule update -q --init --recursive
export LLVM_BUILD_DIR=$D/llvm-project/build
cmake -G Ninja -S neura -B neura/build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ \
  -DPython3_EXECUTABLE=$PY -DPython_EXECUTABLE=$PY -DMLIR_DIR=$LLVM_BUILD_DIR/lib/cmake/mlir
cmake --build neura/build -j 8
echo BUILD_DONE
