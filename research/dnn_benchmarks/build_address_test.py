"""Compile a bit-enumerating oracle against the actual Simulator Instruction object."""
import argparse,json,shlex,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);build=a.source/'TOGSim/build'
entry=next(x for x in json.loads((build/'compile_commands.json').read_text()) if x['file'].endswith('/Instruction.cc'))
args=shlex.split(entry['command']);oi=args.index('-o');args[oi+1]=str(a.out/'test.o')
args[args.index('-c')+1]=str(Path(__file__).parent/'cpp/test_dma_addresses.cc')
subprocess.run(args,cwd=entry['directory'],check=True)
link=shlex.split((build/'src/CMakeFiles/Simulator.dir/link.txt').read_text());tail=link[link.index('-o')+2:]
subprocess.run([link[0],str(a.out/'test.o'),str(build/'src/CMakeFiles/Simulator.dir/Instruction.cc.o'),'-o',str(a.out/'test_dma'),*tail],cwd=build/'src',check=True)
r=subprocess.run([str(a.out/'test_dma')],cwd=a.out,check=True,capture_output=True,text=True)
(a.out/'stdout.txt').write_text(r.stdout);(a.out/'result.json').write_text(r.stdout.splitlines()[-1]+'\n');print(r.stdout)
