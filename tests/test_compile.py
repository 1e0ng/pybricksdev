# SPDX-License-Identifier: MIT
# Copyright (c) 2022 The Pybricks Authors


import os
import struct
from tempfile import NamedTemporaryFile, TemporaryDirectory

import pytest

from pybricksdev.compile import compile_file, compile_multi_file


@pytest.mark.parametrize("abi", [5, 6])
@pytest.mark.asyncio
async def test_compile_file(abi: int):
    with NamedTemporaryFile("w", delete=False, suffix=".py") as f:
        try:
            f.write("print('test')")
            f.close()

            mpy = await compile_file(
                os.path.dirname(f.name), os.path.basename(f.name), abi=abi
            )

            magic, abi_ver, flags, int_bits = struct.unpack_from("<BBBB", mpy)

            assert chr(magic) == "M"
            assert abi_ver == abi
            assert flags == 0
            assert int_bits == 31
        finally:
            os.unlink(f.name)


@pytest.mark.parametrize("abi", [5, 6])
@pytest.mark.asyncio
async def test_compile_multi_file_empty_script(abi: int):
    with NamedTemporaryFile("w", delete=False, suffix=".py") as f:
        try:
            # Empty file is already created
            f.close()
            # For an empty script, compile_multi_file should return the same as compile_file
            # as it's a single file with no imports.
            expected_mpy = await compile_file(
                os.path.dirname(f.name), os.path.basename(f.name), abi=abi
            )
            actual_mpy = await compile_multi_file(f.name, abi=abi)
            assert actual_mpy == expected_mpy
        finally:
            os.unlink(f.name)


@pytest.mark.parametrize("abi", [5, 6])
@pytest.mark.asyncio
async def test_compile_multi_file_single_script_no_imports(abi: int):
    with NamedTemporaryFile("w", delete=False, suffix=".py") as f:
        script_content = "print('Hello from single script')"
        try:
            f.write(script_content)
            f.close()

            # Compile with compile_file to get the raw mpy data
            expected_mpy = await compile_file(
                os.path.dirname(f.name), os.path.basename(f.name), abi=abi
            )

            # Compile with compile_multi_file
            actual_mpy = await compile_multi_file(f.name, abi=abi)

            assert actual_mpy == expected_mpy
        finally:
            os.unlink(f.name)


@pytest.mark.parametrize("abi", [5, 6])
@pytest.mark.asyncio
async def test_compile_multi_file_with_imports(abi: int):
    with TemporaryDirectory() as temp_dir:
        main_script_content = "import mod; print(mod.GREETING)"
        main_script_path = os.path.join(temp_dir, "main.py")
        with open(main_script_path, "w") as f_main:
            f_main.write(main_script_content)

        module_script_content = 'GREETING = "Hello from module"'
        module_script_path = os.path.join(temp_dir, "mod.py")
        with open(module_script_path, "w") as f_mod:
            f_mod.write(module_script_content)

        # Get raw mpy data for main.py
        # The compile_file function needs dir and filename separately.
        main_mpy = await compile_file(
            temp_dir, "main.py", abi=abi
        )

        # Get raw mpy data for mod.py
        mod_mpy = await compile_file(
            temp_dir, "mod.py", abi=abi
        )

        # Construct expected output
        # The order of files in the output is determined by ModuleFinder,
        # which might not be alphabetical. For a simple import like this,
        # the imported module usually comes first, then the main script.
        # Let's assume 'mod' then 'main' for now. If the test fails,
        # we might need to inspect the actual order ModuleFinder uses or
        # make the assertion order-agnostic if possible.
        #
        # Update: Based on how ModuleFinder works and is used in compile_multi_file,
        # it processes the main script first, then its dependencies.
        # So, 'main' should appear before 'mod' if 'main' is the entry point.
        # However, the internal dictionary order of finder.modules might vary.
        # Let's check the actual output of compile_multi_file and adapt.
        # The current implementation of compile_multi_file iterates finder.modules.items()
        # which can be non-deterministic for Python < 3.7. For >=3.7, dicts are ordered.
        # Let's assume for now the order will be main, then mod based on typical ModuleFinder behavior
        # when main.py is the script run.

        # If 'main' imports 'mod', 'main' is processed, then 'mod' is found.
        # The parts list in compile_multi_file will have 'main' parts then 'mod' parts.

        expected_output_parts = []
        # Part 1: __main__.py (ModuleFinder names the main script __main__)
        expected_output_parts.append(len(main_mpy).to_bytes(4, "little"))
        expected_output_parts.append(b"__main__\x00")
        expected_output_parts.append(main_mpy)

        # Part 2: mod.py
        expected_output_parts.append(len(mod_mpy).to_bytes(4, "little"))
        expected_output_parts.append(b"mod\x00") 
        expected_output_parts.append(mod_mpy)

        expected_mpy_bundle = b"".join(expected_output_parts)

        # Compile with compile_multi_file
        actual_mpy_bundle = await compile_multi_file(main_script_path, abi=abi)

        # The order should be __main__ first, then its import 'mod'.
        assert actual_mpy_bundle == expected_mpy_bundle
