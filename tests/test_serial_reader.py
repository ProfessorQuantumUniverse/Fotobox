"""Tests for the serial reader module."""

from unittest.mock import MagicMock, patch

import pytest

from server.serial_reader import SerialReader


class TestSerialReader:
    """Tests for SerialReader."""

    def test_init_defaults(self):
        reader = SerialReader()
        assert reader.port == "/dev/ttyUSB0"
        assert reader.baud == 9600
        assert reader.on_message is None
        assert not reader.is_running

    def test_init_custom(self):
        cb = MagicMock()
        reader = SerialReader(port="/dev/ttyACM0", baud=115200, on_message=cb)
        assert reader.port == "/dev/ttyACM0"
        assert reader.baud == 115200
        assert reader.on_message is cb

    @patch("server.serial_reader.serial.Serial")
    def test_start_opens_serial(self, mock_serial_cls):
        mock_conn = MagicMock()
        mock_conn.readline.return_value = b""
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader(port="/dev/ttyUSB0")
        reader.start()
        assert reader.is_running

        mock_serial_cls.assert_called_once_with("/dev/ttyUSB0", 9600, timeout=1)

        reader.stop()
        assert not reader.is_running

    @patch("server.serial_reader.serial.Serial")
    def test_stop_closes_connection(self, mock_serial_cls):
        mock_conn = MagicMock()
        mock_conn.readline.return_value = b""
        mock_conn.is_open = True
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader()
        reader.start()
        reader.stop()

        mock_conn.close.assert_called_once()

    def test_start_serial_exception(self):
        import serial
        with patch("server.serial_reader.serial.Serial", side_effect=serial.SerialException("port error")):
            reader = SerialReader()
            with pytest.raises(serial.SerialException):
                reader.start()
            assert not reader.is_running

    @patch("server.serial_reader.serial.Serial")
    def test_message_callback(self, mock_serial_cls):
        """Verify the callback fires when data arrives."""
        import time

        messages = []
        mock_conn = MagicMock()
        # Return one message then empty reads
        mock_conn.readline.side_effect = [
            b"countdown_complete\n",
            b"",
            b"",
        ]
        mock_conn.is_open = True
        mock_serial_cls.return_value = mock_conn

        reader = SerialReader(on_message=lambda m: messages.append(m))
        reader.start()
        time.sleep(0.3)
        reader.stop()

        assert "countdown_complete" in messages
