"""Tests for the pybricks connection module."""

import asyncio
import contextlib
import os
import tempfile
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest
from reactivex.subject import Subject

from pybricksdev.connections.pybricks import (
    ConnectionState,
    HubCapabilityFlag,
    HubKind,
    PybricksHubBLE,
    StatusFlag,
)


class TestPybricksHub:
    """Tests for the PybricksHub base class functionality."""

    @pytest.mark.asyncio
    async def test_download_modern_protocol(self):
        """Test downloading with modern protocol and capability flags."""
        hub = PybricksHubBLE("mock_device")
        hub._mpy_abi_version = 6
        hub._client = AsyncMock()
        hub.get_capabilities = AsyncMock(return_value={"pybricks": {"mpy": True}})
        hub.download_user_program = AsyncMock()
        type(hub.connection_state_observable).value = PropertyMock(
            return_value=ConnectionState.CONNECTED
        )
        hub._capability_flags = HubCapabilityFlag.USER_PROG_MULTI_FILE_MPY6

        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            await hub.download(temp_path)
            hub.download_user_program.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_legacy_firmware(self):
        """Test downloading with legacy firmware."""
        hub = PybricksHubBLE("mock_device")
        hub._mpy_abi_version = None  # Legacy firmware
        hub._client = AsyncMock()
        hub.download_user_program = AsyncMock()
        hub.hub_kind = HubKind.BOOST
        type(hub.connection_state_observable).value = PropertyMock(
            return_value=ConnectionState.CONNECTED
        )
        hub._capability_flags = HubCapabilityFlag.USER_PROG_MULTI_FILE_MPY6

        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            await hub.download(temp_path)
            hub.download_user_program.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_unsupported_capabilities(self):
        """Test downloading when hub doesn't support required capabilities."""
        hub = PybricksHubBLE("mock_device")
        hub._mpy_abi_version = 6
        hub._client = AsyncMock()
        hub.get_capabilities = AsyncMock(return_value={"pybricks": {"mpy": False}})
        type(hub.connection_state_observable).value = PropertyMock(
            return_value=ConnectionState.CONNECTED
        )
        hub._capability_flags = 0

        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            with pytest.raises(
                RuntimeError,
                match="Hub is not compatible with any of the supported file formats",
            ):
                await hub.download(temp_path)

    @pytest.mark.asyncio
    async def test_download_compile_error(self):
        """Test handling compilation errors."""
        hub = PybricksHubBLE("mock_device")
        hub._mpy_abi_version = 6
        hub._client = AsyncMock()
        hub.get_capabilities = AsyncMock(return_value={"pybricks": {"mpy": True}})
        type(hub.connection_state_observable).value = PropertyMock(
            return_value=ConnectionState.CONNECTED
        )
        hub._capability_flags = HubCapabilityFlag.USER_PROG_MULTI_FILE_MPY6
        hub._max_user_program_size = 1000  # Set a reasonable size limit

        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test'  # Missing closing parenthesis")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Mock compile_multi_file to raise SyntaxError
            stack.enter_context(
                patch(
                    "pybricksdev.connections.pybricks.compile_multi_file",
                    side_effect=SyntaxError("invalid syntax"),
                )
            )

            with pytest.raises(SyntaxError, match="invalid syntax"):
                await hub.download(temp_path)

    @pytest.mark.asyncio
    async def test_run_modern_protocol(self):
        """Test running a program with modern protocol."""
        hub = PybricksHubBLE("mock_device")
        hub._mpy_abi_version = None  # Use modern protocol
        hub._client = AsyncMock()
        hub.client = AsyncMock()
        hub.get_capabilities = AsyncMock(return_value={"pybricks": {"mpy": True}})
        hub.download_user_program = AsyncMock()
        hub.start_user_program = AsyncMock()
        hub.write_gatt_char = AsyncMock()
        type(hub.connection_state_observable).value = PropertyMock(
            return_value=ConnectionState.CONNECTED
        )
        hub._capability_flags = HubCapabilityFlag.USER_PROG_MULTI_FILE_MPY6
        hub.hub_kind = HubKind.BOOST

        # Mock the status observable to simulate program start and stop
        status_subject = Subject()
        hub.status_observable = status_subject
        hub._stdout_line_queue = asyncio.Queue()
        hub._enable_line_handler = True

        with contextlib.ExitStack() as stack:
            # Create and manage temporary file
            temp = stack.enter_context(
                tempfile.NamedTemporaryFile(suffix=".py", mode="w+", delete=False)
            )
            temp.write("print('test')")
            temp_path = temp.name
            stack.callback(os.unlink, temp_path)

            # Start the run task
            run_task = asyncio.create_task(hub.run(temp_path))

            # Simulate program start
            await asyncio.sleep(0.1)
            status_subject.on_next(StatusFlag.USER_PROGRAM_RUNNING)

            # Simulate program stop after a short delay
            await asyncio.sleep(0.1)
            status_subject.on_next(0)  # Clear all flags

            # Wait for run task to complete
            await run_task

            # Verify the expected calls were made
            hub.download_user_program.assert_called_once()
            hub.start_user_program.assert_called_once()


class TestPybricksHubUSB:
    """Tests for the PybricksHubUSB class."""

    @pytest.mark.asyncio
    @patch("pybricksdev.connections.pybricks.find_descriptor")
    @patch("pybricksdev.connections.pybricks.get_descriptor")
    @patch("usb.core.Device")
    async def test_client_connect_invalid_bos_descriptor(
        self, mock_usb_device_class, mock_get_descriptor, mock_find_descriptor
    ):
        """Test _client_connect with an invalid BOS descriptor."""
        mock_device_instance = mock_usb_device_class.return_value

        # Mock the two endpoints
        mock_ep_in = AsyncMock()
        mock_ep_out = AsyncMock()
        mock_ep_out.wMaxPacketSize = 64  # Example packet size

        mock_find_descriptor.side_effect = [mock_ep_in, mock_ep_out]

        # Mock get_descriptor calls
        # First call: get length of BOS descriptor
        # struct BOSDescriptor {
        #   uint8_t bLength;
        #   uint8_t bDescriptorType; // 0x0F
        #   uint16_t wTotalLength;
        #   uint8_t bNumDeviceCaps;
        # }
        # For this test, we only need wTotalLength to be reasonable.
        # Let's say the total length is 10 (5 for header + 5 for one capability header)
        mock_get_descriptor.side_effect = [
            # First call to get BOS descriptor length (bLength, bDescriptorType, wTotalLength, bNumDeviceCaps)
            # wTotalLength = 5 (header) + 5 (one cap header) = 10
            # For the first call, only wTotalLength (at offset 2, size 2) and bLength (offset 0, size 1) are used.
            # The first byte read is offset, then _, bos_len, _
            # So, we need to return bytes that parse correctly to (ANY_BYTE, ANY_BYTE, desired_bos_len, ANY_BYTE)
            # Let's make desired_bos_len = 10.
            # struct.pack("<BBHB", offset_val, placeholder, bos_len_val, placeholder_num_caps)
            # The code uses: (ofst, _, bos_len, _) = struct.unpack("<BBHB", bos_descriptor)
            # So the mock should return bytes that unpack to this.
            # Let the first descriptor be 5 bytes long (bLength=5)
            # bDescriptorType = 0x0F (BOS)
            # wTotalLength = 10
            # bNumDeviceCaps = 1
            struct.pack("<BBHB", 5, 0x0F, 10, 1), # Correctly returns total length of 10
            # Second call: get full BOS descriptor
            # This will be parsed in a loop.
            # First iteration: (len, desc_type, cap_type)
            # We want desc_type to be != 0x10 to trigger the error.
            # Let len = 5 (size of this descriptor part), desc_type = 0xFE (invalid), cap_type = 0x05 (platform)
            # The rest of the 10 bytes can be anything, e.g., padding.
            struct.pack("<BBB", 5, 0xFE, 0x05) + b"\x00\x00\x00\x00\x00", # len=5, desc_type=0xFE (invalid)
        ]

        hub = PybricksHubUSB(mock_device_instance)

        with pytest.raises(RuntimeError, match="Expected Device Capability descriptor"):
            await hub._client_connect()

        # Check that device methods were called
        mock_device_instance.reset.assert_called_once()
        mock_device_instance.set_configuration.assert_called_once()
        mock_device_instance.get_active_configuration.assert_called_once()

        # Check that get_descriptor was called twice with correct args
        assert mock_get_descriptor.call_count == 2
        mock_get_descriptor.assert_any_call(mock_device_instance, 5, 0x0F, 0) # Get length
        mock_get_descriptor.assert_any_call(mock_device_instance, 10, 0x0F, 0) # Get full descriptor

        # Check find_descriptor calls
        assert mock_find_descriptor.call_count == 2
