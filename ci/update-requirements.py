#!/usr/bin/env python3

"""
This script updates all of the requirements-*.txt files in this directory
with the most recent package versions.

It uses pip-compile (https://github.com/jazzband/pip-tools) and pkginfo,
so install these dependencies before running it.
"""

import argparse
import os
import re
import subprocess # nosec - disable B404:import-subprocess check
import sys

from pathlib import Path
from pkginfo import Wheel

# Package dependencies can vary depending on the Python version.
# We thus have to run pip-compile with the lowest Python version that
# the project supports.
EXPECTED_PYTHON_VERSION = (3, 6)

repo_root = Path(__file__).resolve().parent.parent
script_name = Path(__file__).name

def fixup_req_file(req_path, path_placeholders):
    contents = req_path.read_text()

    for path, placeholder in path_placeholders:
        contents = contents.replace(f'-r {path}/', f'-r ${{{placeholder}}}/')
        contents = contents.replace(f'({path}/', f'(${{{placeholder}}}/')

    contents = "# use {} to update this file\n\n".format(script_name) + contents
    req_path.write_text(contents)

def pip_compile(target, *sources, upgrade=False):
    print('updating {}...'.format(target), flush=True)

    # Use --no-header, since the OpenVINO install path may vary between machines,
    # so it should not be embedded in the output file. Also, this script makes
    # the information in pip-compile's headers redundant.

    subprocess.run(
        [sys.executable, '-mpiptools', 'compile',
            *(['--upgrade'] if upgrade else []),
            '--no-header', '--quiet', '-o', target, '--', *map(str, sources)],
        check=True, cwd=str(repo_root))

def update_openvino_dev_reqs():
    package_downloading_stdout = subprocess.run(
        [sys.executable, '-m', 'pip', 'download', 'openvino-dev', '--no-deps'],
        check=True, stdout=subprocess.PIPE, universal_newlines=True).stdout

    wheel_name = re.search(r'openvino\S*\.whl', package_downloading_stdout).group(0)
    wheel = Wheel(wheel_name)
    reqs_list = sorted(wheel.requires_dist)

    with open("requirements-openvino-dev.in", "w", encoding="UTF-8") as f:
        f.write("\n".join(reqs_list) + "\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--upgrade', action='store_true', help='Bump package versions')
    args = parser.parse_args()

    if sys.version_info[:2] != EXPECTED_PYTHON_VERSION:
        sys.exit("run this with Python {}".format('.'.join(map(str, EXPECTED_PYTHON_VERSION))))

    if 'INTEL_OPENVINO_DIR' not in os.environ:
        sys.exit("run OpenVINO toolkit's setupvars.sh before this")

    openvino_dir = Path(os.environ['INTEL_OPENVINO_DIR'])

    update_openvino_dev_reqs()

    def pc(target, *sources):
        pip_compile(target, *sources, upgrade=args.upgrade)
        fixup_req_file(repo_root / target, [(openvino_dir, 'INTEL_OPENVINO_DIR')])

    pc('ci/requirements-ac.txt',
        'tools/accuracy_checker/requirements-core.in', 'tools/accuracy_checker/requirements.in')
    pc('ci/requirements-ac-test.txt',
        'tools/accuracy_checker/requirements.in', 'tools/accuracy_checker/requirements-test.in',
        'tools/accuracy_checker/requirements-core.in')
    pc('ci/requirements-check-basics.txt',
       'ci/requirements-check-basics.in', 'ci/requirements-documentation.in')
    pc('ci/requirements-conversion.txt',
        *(f'tools/model_tools/requirements-{suffix}.in' for suffix in ['pytorch', 'tensorflow']),
        *(openvino_dir / f'deployment_tools/model_optimizer/requirements_{suffix}.txt'
            for suffix in ['caffe', 'mxnet', 'onnx', 'tf2']))
    pc('ci/requirements-demos.txt',
        'demos/requirements.txt', openvino_dir / 'python/requirements.txt')
    pc('ci/requirements-downloader.txt',
        'tools/model_tools/requirements.in')
    pc('ci/requirements-quantization.txt',
        'tools/accuracy_checker/requirements-core.in', 'tools/accuracy_checker/requirements.in',
        openvino_dir / 'deployment_tools/tools/post_training_optimization_toolkit/setup.py',
        openvino_dir / 'deployment_tools/model_optimizer/requirements_kaldi.txt')
    pc('ci/requirements-openvino-dev.txt', 'ci/requirements-openvino-dev.in')

if __name__ == '__main__':
    main()
