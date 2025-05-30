"""Tests for the pybricksdev CLI commands."""

import argparse
import contextlib
import io
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from pybricksdev.cli import Download, Run, Tool


class TestTool:
    """Tests for the base Tool class."""

    def test_is_abstract(self):
        """Test that Tool is an abstract base class."""
        with pytest.raises(TypeError):
            Tool()


class TestDownload:
    """Tests for the Download command."""

    def test_add_parser(self):
        """Test that the parser is set up correctly."""
        # Create a subparsers object
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()

        # Add the download command
        download = Download()
        download.add_parser(subparsers)

        # Verify the parser was created with correct arguments
        assert "download" in subparsers.choices
        parser = subparsers.choices["download"]
        assert parser.tool is download

        # Test that required arguments are present
        mock_file = mock_open(read_data="print('test')")
        mock_file.return_value.name = "test.py"
        with patch("builtins.open", mock_file):
            args = parser.parse_args(["ble", "test.py"])
            assert args.conntype == "ble"
            assert args.file.name == "test.py"
            assert args.name is None

        # Test with optional name argument
        mock_file = mock_open(read_data="print('test')")
        mock_file.return_value.name = "test.py"
        with patch("builtins.open", mock_file):
            args = parser.parse_args(["ble", "test.py", "-n", "MyHub"])
            assert args.name == "MyHub"

        # Test that invalid connection type is rejected
        with pytest.raises(SystemExit):
            parser.parse_args(["invalid", "test.py"])

    @pytest.mark.asyncio
    async def test_download_ble(self):
        """Test running the download command with BLE connection."""
        # Create a mock hub
        mock_hub = AsyncMock()
        mock_hub._mpy_abi_version = 6
        mock_hub.download = AsyncMock()

        # Set up mocks using ExitStack
        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Create args
            args = argparse.Namespace(
                conntype="ble",
                file=open(temp_path, "r"),
                name="MyHub",
            )

            mock_hub_class = stack.enter_context(
                patch(
                    "pybricksdev.connections.pybricks.PybricksHubBLE",
                    return_value=mock_hub,
                )
            )
            stack.enter_context(
                patch("pybricksdev.ble.find_device", return_value="mock_device")
            )

            # Run the command
            download = Download()
            await download.run(args)

            # Verify the hub was created and used correctly
            mock_hub_class.assert_called_once_with("mock_device")
            mock_hub.connect.assert_called_once()
            mock_hub.download.assert_called_once()
            mock_hub.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_usb(self):
        """Test running the download command with USB connection."""
        # Create a mock hub
        mock_hub = AsyncMock()
        mock_hub._mpy_abi_version = 6
        mock_hub.download = AsyncMock()

        # Set up mocks using ExitStack
        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Create args
            args = argparse.Namespace(
                conntype="usb",
                file=open(temp_path, "r"),
                name=None,
            )

            mock_hub_class = stack.enter_context(
                patch(
                    "pybricksdev.connections.pybricks.PybricksHubUSB",
                    return_value=mock_hub,
                )
            )
            stack.enter_context(patch("usb.core.find", return_value="mock_device"))

            # Run the command
            download = Download()
            await download.run(args)

            # Verify the hub was created and used correctly
            mock_hub_class.assert_called_once_with("mock_device")
            mock_hub.connect.assert_called_once()
            mock_hub.download.assert_called_once()
            mock_hub.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_ssh(self):
        """Test running the download command with SSH connection."""
        # Create a mock hub
        mock_hub = AsyncMock()
        mock_hub.download = AsyncMock()

        # Set up mocks using ExitStack
        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Create args
            args = argparse.Namespace(
                conntype="ssh",
                file=open(temp_path, "r"),
                name="ev3dev.local",
            )

            mock_hub_class = stack.enter_context(
                patch(
                    "pybricksdev.connections.ev3dev.EV3Connection",
                    return_value=mock_hub,
                )
            )
            stack.enter_context(
                patch("socket.gethostbyname", return_value="192.168.1.1")
            )

            # Run the command
            download = Download()
            await download.run(args)

            # Verify the hub was created and used correctly
            mock_hub_class.assert_called_once_with("192.168.1.1")
            mock_hub.connect.assert_called_once()
            mock_hub.download.assert_called_once()
            mock_hub.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_ssh_no_name(self):
        """Test that SSH connection requires a name."""
        # Set up mocks using ExitStack
        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Create args without name
            args = argparse.Namespace(
                conntype="ssh",
                file=open(temp_path, "r"),
                name=None,
            )

            # Run the command and verify it exits
            download = Download()
            with pytest.raises(SystemExit, match="1"):
                await download.run(args)

    @pytest.mark.asyncio
    async def test_download_stdin(self):
        """Test running the download command with stdin input."""
        # Create a mock hub
        mock_hub = AsyncMock()
        mock_hub._mpy_abi_version = 6
        mock_hub.download = AsyncMock()

        # Create a mock stdin
        mock_stdin = io.StringIO("print('test')")
        mock_stdin.buffer = io.BytesIO(b"print('test')")
        mock_stdin.name = "<stdin>"

        # Create args
        args = argparse.Namespace(
            conntype="ble",
            file=mock_stdin,
            name="MyHub",
        )

        # Set up mocks using ExitStack
        with contextlib.ExitStack() as stack:
            mock_hub_class = stack.enter_context(
                patch(
                    "pybricksdev.connections.pybricks.PybricksHubBLE",
                    return_value=mock_hub,
                )
            )
            stack.enter_context(
                patch("pybricksdev.ble.find_device", return_value="mock_device")
            )
            mock_temp = stack.enter_context(patch("tempfile.NamedTemporaryFile"))
            mock_temp.return_value.__enter__.return_value.name = "/tmp/test.py"

            # Run the command
            download = Download()
            await download.run(args)

            # Verify the hub was created and used correctly
            mock_hub_class.assert_called_once_with("mock_device")
            mock_hub.connect.assert_called_once()
            mock_hub.download.assert_called_once()
            mock_hub.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_connection_error(self):
        """Test handling connection errors."""
        # Create a mock hub that raises an error during connect
        mock_hub = AsyncMock()
        mock_hub.connect.side_effect = RuntimeError("Connection failed")

        # Set up mocks using ExitStack
        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Create args
            args = argparse.Namespace(
                conntype="ble",
                file=open(temp_path, "r"),
                name="MyHub",
            )

            stack.enter_context(
                patch(
                    "pybricksdev.connections.pybricks.PybricksHubBLE",
                    return_value=mock_hub,
                )
            )
            stack.enter_context(
                patch("pybricksdev.ble.find_device", return_value="mock_device")
            )

            # Run the command and verify it raises the error
            download = Download()
            with pytest.raises(RuntimeError, match="Connection failed"):
                await download.run(args)

            # Verify disconnect was not called since connection failed
            mock_hub.disconnect.assert_not_called()


class TestRun:
    """Tests for the Run command."""

    def test_add_parser(self):
        """Test that the parser is set up correctly."""
        # Create a subparsers object
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()

        # Add the run command
        run_cmd = Run()
        run_cmd.add_parser(subparsers)

        # Verify the parser was created with correct arguments
        assert "run" in subparsers.choices
        cmd_parser = subparsers.choices["run"]
        assert cmd_parser.tool is run_cmd

        # Test that required arguments are present and wait defaults to True
        mock_file = mock_open(read_data="print('test')")
        mock_file.return_value.name = "test.py"
        with patch("builtins.open", mock_file):
            args = cmd_parser.parse_args(["ble", "test.py"])
            assert args.conntype == "ble"
            assert args.file.name == "test.py"
            assert args.name is None
            assert args.wait is True  # Default

        # Test with optional name argument
        mock_file = mock_open(read_data="print('test')")
        mock_file.return_value.name = "test.py"
        with patch("builtins.open", mock_file):
            args = cmd_parser.parse_args(["ble", "test.py", "-n", "MyHub"])
            assert args.name == "MyHub"

        # Test --no-wait argument
        mock_file = mock_open(read_data="print('test')")
        mock_file.return_value.name = "test.py"
        with patch("builtins.open", mock_file):
            args = cmd_parser.parse_args(["ble", "test.py", "--no-wait"])
            assert args.wait is False

        # Test --wait argument explicitly
        mock_file = mock_open(read_data="print('test')")
        mock_file.return_value.name = "test.py"
        with patch("builtins.open", mock_file):
            args = cmd_parser.parse_args(["ble", "test.py", "--wait"])
            assert args.wait is True

        # Test that invalid connection type is rejected
        with pytest.raises(SystemExit):
            cmd_parser.parse_args(["invalid", "test.py"])

    @pytest.mark.asyncio
    async def test_run_ble(self):
        """Test running the run command with BLE connection."""
        run_cmd = Run()

        for wait_value in [True, False]:
            # Create a mock hub
            mock_hub = AsyncMock()
            mock_hub.run = AsyncMock()

            with contextlib.ExitStack() as stack:
                temp = stack.enter_context(
                    tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
                )
                temp.write("print('test')")
                temp_path = temp.name
                stack.callback(os.unlink, temp_path)

                # Create args
                # We need to close and reopen the file for each iteration if it's consumed,
                # but argparse opens it. For this test, direct use of path is fine.
                # The actual command will receive file path from argparse which handles opening.
                # For the purpose of testing `run_cmd.run`, providing a path-like object or
                # a mock that behaves like a file object is key.
                # The Download tests use open(temp_path, "r"). Let's stick to that for consistency.
                # The file object itself is not directly passed to hub.run, but its name attribute is.
                file_mock = mock_open(read_data="print('test')")
                file_mock.return_value.name = temp_path

                with patch("builtins.open", file_mock):
                    args = argparse.Namespace(
                        conntype="ble",
                        file=open(temp_path, "r"), # This open is mocked by file_mock
                        name="MyHub",
                        wait=wait_value,
                    )

                mock_hub_class = stack.enter_context(
                    patch(
                        "pybricksdev.connections.pybricks.PybricksHubBLE",
                        return_value=mock_hub,
                    )
                )
                stack.enter_context(
                    patch("pybricksdev.ble.find_device", return_value="mock_device")
                )

                await run_cmd.run(args)

                mock_hub_class.assert_called_once_with("mock_device")
                mock_hub.connect.assert_called_once()
                # The actual file path (name) is extracted from the file object by the command
                mock_hub.run.assert_called_once_with(temp_path, wait=wait_value)
                mock_hub.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_usb(self):
        """Test running the run command with USB connection."""
        run_cmd = Run()

        for wait_value in [True, False]:
            mock_hub = AsyncMock()
            mock_hub.run = AsyncMock()

            with contextlib.ExitStack() as stack:
                temp = stack.enter_context(
                    tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
                )
                temp.write("print('test')")
                temp_path = temp.name
                stack.callback(os.unlink, temp_path)

                file_mock = mock_open(read_data="print('test')")
                file_mock.return_value.name = temp_path

                with patch("builtins.open", file_mock):
                    args = argparse.Namespace(
                        conntype="usb",
                        file=open(temp_path, "r"),
                        name=None,
                        wait=wait_value,
                    )

                mock_hub_class = stack.enter_context(
                    patch(
                        "pybricksdev.connections.pybricks.PybricksHubUSB",
                        return_value=mock_hub,
                    )
                )
                stack.enter_context(patch("usb.core.find", return_value="mock_device"))

                await run_cmd.run(args)

                mock_hub_class.assert_called_once_with("mock_device")
                mock_hub.connect.assert_called_once()
                mock_hub.run.assert_called_once_with(temp_path, wait=wait_value)
                mock_hub.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_connection_error(self):
        """Test handling connection errors during run command."""
        run_cmd = Run()

        # Create a mock hub that raises an error during connect
        mock_hub = AsyncMock()
        mock_hub.connect.side_effect = RuntimeError("Connection failed")
        mock_hub.run = AsyncMock() # Should not be called
        mock_hub.disconnect = AsyncMock() # Should not be called

        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Create args (using BLE as an example)
            # The actual open call for the file will be handled by argparse normally.
            # For this test, we ensure that the file argument is present.
            args = argparse.Namespace(
                conntype="ble",
                file=open(temp_path, "r"),
                name="MyHub",
                wait=True, # wait value should not matter
            )

            # Patch the hub connection and device finding
            stack.enter_context(
                patch(
                    "pybricksdev.connections.pybricks.PybricksHubBLE",
                    return_value=mock_hub,
                )
            )
            stack.enter_context(
                patch("pybricksdev.ble.find_device", return_value="mock_device")
            )

            # Run the command and verify it raises the error
            with pytest.raises(RuntimeError, match="Connection failed"):
                await run_cmd.run(args)

            # Verify connect was called (and raised an error)
            mock_hub.connect.assert_called_once()
            # Verify run and disconnect were not called since connection failed
            mock_hub.run.assert_not_called()
            mock_hub.disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_ssh_no_name(self):
        """Test that SSH connection for run command requires a name."""
        run_cmd = Run()

        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Mock gethostbyname to ensure it's not called
            mock_gethostbyname = stack.enter_context(patch("socket.gethostbyname"))
            # Mock EV3Connection to ensure it's not instantiated or used
            mock_ev3_connection_class = stack.enter_context(
                patch("pybricksdev.connections.ev3dev.EV3Connection")
            )

            # Create args without name
            # The file needs to be opened for argparse, but we mock builtins.open
            # to avoid actual file operations if preferred for this specific test.
            # However, following test_download_ssh_no_name, it uses a real temp file.
            args = argparse.Namespace(
                conntype="ssh",
                file=open(temp_path, "r"), # Argparse expects an open file
                name=None,
                wait=True, # wait value should not matter
            )

            # Run the command and verify it exits
            with pytest.raises(SystemExit, match="1"):
                await run_cmd.run(args)

            # Verify that connection attempts were not made
            mock_gethostbyname.assert_not_called()
            mock_ev3_connection_class.assert_not_called()
            # Also check that if an instance was somehow created, its methods weren't called
            if mock_ev3_connection_class.return_value:
                mock_ev3_connection_class.return_value.connect.assert_not_called()
                mock_ev3_connection_class.return_value.run.assert_not_called()
                mock_ev3_connection_class.return_value.disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_stdin(self):
        """Test running the run command with stdin input."""
        run_cmd = Run()
        stdin_content = "print('test from stdin')"
        stdin_content_bytes = stdin_content.encode("utf-8")
        fake_temp_path = "/tmp/fake_stdin_script.py"

        for wait_value in [True, False]:
            # Create a mock hub
            mock_hub = AsyncMock()
            mock_hub.run = AsyncMock()

            # Create a mock stdin
            mock_stdin = io.StringIO(stdin_content)
            mock_stdin.buffer = io.BytesIO(stdin_content_bytes) # type: ignore
            mock_stdin.name = "<stdin>"

            args = argparse.Namespace(
                conntype="ble",  # Using BLE as an example
                file=mock_stdin,
                name="MyHub",
                wait=wait_value,
            )

            with contextlib.ExitStack() as stack:
                mock_hub_class = stack.enter_context(
                    patch(
                        "pybricksdev.connections.pybricks.PybricksHubBLE",
                        return_value=mock_hub,
                    )
                )
                stack.enter_context(
                    patch("pybricksdev.ble.find_device", return_value="mock_device")
                )
                
                # Mock tempfile.NamedTemporaryFile
                mock_temp_file_constructor = stack.enter_context(
                    patch("tempfile.NamedTemporaryFile")
                )
                # Configure the mock for context manager behavior
                mock_temp_file_instance = mock_temp_file_constructor.return_value.__enter__.return_value
                mock_temp_file_instance.name = fake_temp_path
                # temp_file.write is synchronous in the Run command
                mock_temp_file_instance.write = MagicMock()

                await run_cmd.run(args)

                mock_hub_class.assert_called_once_with("mock_device")
                mock_hub.connect.assert_called_once()
                
                # Verify tempfile usage for stdin
                # The Run command should open a temp file, write stdin's content to it, then use that file.
                mock_temp_file_constructor.assert_called_once_with(mode="wb", delete=False, suffix=".py")
                mock_temp_file_instance.write.assert_called_once_with(stdin_content_bytes)
                
                mock_hub.run.assert_called_once_with(fake_temp_path, wait=wait_value)
                mock_hub.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_ssh(self):
        """Test running the run command with SSH connection."""
        run_cmd = Run()

        for wait_value in [True, False]:
            mock_hub = AsyncMock()
            mock_hub.run = AsyncMock()

            with contextlib.ExitStack() as stack:
                temp = stack.enter_context(
                    tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
                )
                temp.write("print('test')")
                temp_path = temp.name
                stack.callback(os.unlink, temp_path)

                file_mock = mock_open(read_data="print('test')")
                file_mock.return_value.name = temp_path
                
                with patch("builtins.open", file_mock):
                    args = argparse.Namespace(
                        conntype="ssh",
                        file=open(temp_path, "r"),
                        name="ev3dev.local",
                        wait=wait_value,
                    )

                mock_hub_class = stack.enter_context(
                    patch(
                        "pybricksdev.connections.ev3dev.EV3Connection",
                        return_value=mock_hub,
                    )
                )
                stack.enter_context(
                    patch("socket.gethostbyname", return_value="192.168.1.1")
                )

                await run_cmd.run(args)

                mock_hub_class.assert_called_once_with("192.168.1.1")
                mock_hub.connect.assert_called_once()
                mock_hub.run.assert_called_once_with(temp_path, wait=wait_value)
                mock_hub.disconnect.assert_called_once()
