#!/usr/bin/env python3

import sys
import argparse
import serial
import struct
import intelhex
import array
import progressbar

# crc_table and crc16 generated from pycrc.
# ./pycrc.py --model crc-16 --algorithm table-driven --generate c
crc_table = [
    0x0000, 0xc0c1, 0xc181, 0x0140, 0xc301, 0x03c0, 0x0280, 0xc241,
    0xc601, 0x06c0, 0x0780, 0xc741, 0x0500, 0xc5c1, 0xc481, 0x0440,
    0xcc01, 0x0cc0, 0x0d80, 0xcd41, 0x0f00, 0xcfc1, 0xce81, 0x0e40,
    0x0a00, 0xcac1, 0xcb81, 0x0b40, 0xc901, 0x09c0, 0x0880, 0xc841,
    0xd801, 0x18c0, 0x1980, 0xd941, 0x1b00, 0xdbc1, 0xda81, 0x1a40,
    0x1e00, 0xdec1, 0xdf81, 0x1f40, 0xdd01, 0x1dc0, 0x1c80, 0xdc41,
    0x1400, 0xd4c1, 0xd581, 0x1540, 0xd701, 0x17c0, 0x1680, 0xd641,
    0xd201, 0x12c0, 0x1380, 0xd341, 0x1100, 0xd1c1, 0xd081, 0x1040,
    0xf001, 0x30c0, 0x3180, 0xf141, 0x3300, 0xf3c1, 0xf281, 0x3240,
    0x3600, 0xf6c1, 0xf781, 0x3740, 0xf501, 0x35c0, 0x3480, 0xf441,
    0x3c00, 0xfcc1, 0xfd81, 0x3d40, 0xff01, 0x3fc0, 0x3e80, 0xfe41,
    0xfa01, 0x3ac0, 0x3b80, 0xfb41, 0x3900, 0xf9c1, 0xf881, 0x3840,
    0x2800, 0xe8c1, 0xe981, 0x2940, 0xeb01, 0x2bc0, 0x2a80, 0xea41,
    0xee01, 0x2ec0, 0x2f80, 0xef41, 0x2d00, 0xedc1, 0xec81, 0x2c40,
    0xe401, 0x24c0, 0x2580, 0xe541, 0x2700, 0xe7c1, 0xe681, 0x2640,
    0x2200, 0xe2c1, 0xe381, 0x2340, 0xe101, 0x21c0, 0x2080, 0xe041,
    0xa001, 0x60c0, 0x6180, 0xa141, 0x6300, 0xa3c1, 0xa281, 0x6240,
    0x6600, 0xa6c1, 0xa781, 0x6740, 0xa501, 0x65c0, 0x6480, 0xa441,
    0x6c00, 0xacc1, 0xad81, 0x6d40, 0xaf01, 0x6fc0, 0x6e80, 0xae41,
    0xaa01, 0x6ac0, 0x6b80, 0xab41, 0x6900, 0xa9c1, 0xa881, 0x6840,
    0x7800, 0xb8c1, 0xb981, 0x7940, 0xbb01, 0x7bc0, 0x7a80, 0xba41,
    0xbe01, 0x7ec0, 0x7f80, 0xbf41, 0x7d00, 0xbdc1, 0xbc81, 0x7c40,
    0xb401, 0x74c0, 0x7580, 0xb541, 0x7700, 0xb7c1, 0xb681, 0x7640,
    0x7200, 0xb2c1, 0xb381, 0x7340, 0xb101, 0x71c0, 0x7080, 0xb041,
    0x5000, 0x90c1, 0x9181, 0x5140, 0x9301, 0x53c0, 0x5280, 0x9241,
    0x9601, 0x56c0, 0x5780, 0x9741, 0x5500, 0x95c1, 0x9481, 0x5440,
    0x9c01, 0x5cc0, 0x5d80, 0x9d41, 0x5f00, 0x9fc1, 0x9e81, 0x5e40,
    0x5a00, 0x9ac1, 0x9b81, 0x5b40, 0x9901, 0x59c0, 0x5880, 0x9841,
    0x8801, 0x48c0, 0x4980, 0x8941, 0x4b00, 0x8bc1, 0x8a81, 0x4a40,
    0x4e00, 0x8ec1, 0x8f81, 0x4f40, 0x8d01, 0x4dc0, 0x4c80, 0x8c41,
    0x4400, 0x84c1, 0x8581, 0x4540, 0x8701, 0x47c0, 0x4680, 0x8641,
    0x8201, 0x42c0, 0x4380, 0x8341, 0x4100, 0x81c1, 0x8081, 0x4040
]

def crc16(data):
    global crc_table

    crc = 0
    for d in data:
        table_index = (crc ^ d) & 0xff;
        crc = (crc_table[table_index] ^ (crc >> 8)) & 0xffff

    return (crc & 0xffff)

def send_packet(ser, pkt):
    retransmits = 0

    while True:
        cmd = b'W' + struct.pack('B', len(pkt)) + pkt
        ser.write(cmd)
        line = None
        while not line:
            line = ser.readline().strip()

        if line.startswith(b'success'):
            #print("#Raw: ", line)
            #print("#XXX Sent cmd {}".format(cmd))
            break
        else:
            #print("#Raw: ", line)
            #print("Retransmitting.")
            retransmits += 1
            pass

    return retransmits

def serial_connect(config):
    ser = serial.Serial('/dev/tty.usbserial-A40188LY', 115200, timeout = 1)

    # Flush the serial buffer.
    while True:
        line = ser.readline().strip()
        if not line:
            break
            print("#Raw: ", line)

    print("Attempting to synchronize!")
    # First, send characters until we get a '?'.
    while True:
        ser.write(b'\0')
        line = ser.readline()
        print("#Raw q: ", line)
        if line == b'?\r\n':
            break

    count = 0
    while True:
        count += 1
        cmd = b'p' + struct.pack('b', count)
        response = b'P' + struct.pack('b', count)

        print("Sending ", cmd)
        ser.write(cmd)
        line = ser.readline().strip()
        print("#Raw r: ", line)

        if line == response:
            print("Synchronized!");
            break
        else:
            while True:
                line = ser.readline().strip()
                if not line:
                    break
                    print("#Raw f: ", line)

    return ser

def read_data(config):
    raw_data = intelhex.IntelHex(config.filename).tobinarray()

    app_temp_size = config.app_size

    # Must pad out the crc calculation with 0xff up to the mem size.
    num_pad_bytes = app_temp_size - len(raw_data)
    pad_data = array.array('B', [0xff] * num_pad_bytes)
    crc = crc16(raw_data + pad_data)

    return (raw_data, crc)

def set_address(ser, address):
    data = [int(b, 16) for b in address.split(':')]
    cmd = b'A' + struct.pack('B' * 5, *data)
    ser.write(cmd)
    line = ser.readline().strip()
    print("#Raw: ", line)

def get_device_info(config, ser):
    print("Switching to info address.")
    set_address(ser, config.info_addr)

    for send_count in range(10):
        #print("Sending 's'")
        send_packet(ser, b"s")
        for receive_count in range(3):
            #print(".")
            line = ser.readline().strip()
            #print("#Raw r: ", line)
            if line.startswith(b"R("):
                (header, data_bytes) = line.split(b':')
                (pkt_len, pipe) = header[2:-1].split(b',')
                if int(pkt_len) != 8:
                    error = "Data length is wrong! ({} != 8)".format(pkt_len)
                    raise Exception(error)

                # Parse the bytes.
                raw_data = struct.unpack("!cBBBHH", data_bytes)
                msg_id = raw_data[0]
                device_id = (raw_data[1], raw_data[2], raw_data[3])
                page_size = raw_data[4]
                app_size_pages = raw_data[5]
                app_size = app_size_pages * page_size

                if msg_id != b's':
                    error = "Invalid message id! ({} != s)".format(msg_id)
                    raise Exception(error)

                print("Device id {:x}.{:x}.{:x}".format(device_id[0],
                                                        device_id[1],
                                                        device_id[2]))
                print("Page size {}".format(page_size))
                print("App size {}".format(app_size))

                if ((config.device_id != device_id) or
                    (config.app_section_size // 2 != app_size) or
                    (config.page_size != page_size)):

                    raise Exception("Device metadata mismatch!")

                config.page_size = page_size
                config.app_size = app_size

                return

    raise Exception("Unable to contact device!")



def send_data(config, ser, raw_data, crc):
    print("Transmitting {}: {} bytes, {:x} crc"
          .format(config.filename, len(raw_data), crc))

    total_retransmits = 0

    # Erase.
    total_retransmits += send_packet(ser, b"e")

    # Send the data.
    page_size = config.page_size
    chunk_size = 29

    total_len = len(raw_data)
    transmitted = 0

    widgets = ['Transferring: ',
               progressbar.widgets.Percentage(), ' ',
               progressbar.widgets.Bar(), ' ',
               progressbar.widgets.FileTransferSpeed(), ' ',
               progressbar.widgets.ETA()]
    pbar = progressbar.ProgressBar(widgets = widgets, maxval = total_len)
    pbar.start()

    pages = [raw_data[i:i + page_size]
             for i in range(0, len(raw_data), page_size)]
    for page in pages:
        page_offset = 0
        chunks = [page[i:i + chunk_size]
                  for i in range(0, len(page), chunk_size)]
        for chunk in chunks:
            # Send a single chunk.
            total_retransmits += send_packet(ser,
                                             b"B" +
                                             struct.pack('<H', page_offset) +
                                             chunk)
            page_offset += len(chunk)

            transmitted += len(chunk)
            #print("Transmitted {} of {}".format(transmitted, total_len))
            pbar.update(transmitted)

        # Commit this page.
        total_retransmits += send_packet(ser, b"m")

    pbar.finish()

    # Commit the data.
    pkt = b"w" + struct.pack('<H', crc)
    total_retransmits += send_packet(ser, pkt)

    print("Retransmitted {} times.".format(total_retransmits))

def get_part_config(config):
    # XXX Could just read the avrdude config for this.
    parts = {'atxmega32a4u': {'device_id': (0x41, 0x95, 0x1E),
                              'app_section_size': 32768,
                              'page_size': 256},
             'atxmega128a4u': {'device_id': (0x46, 0x97, 0x1E),
                               'app_section_size': 131072,
                               'page_size': 256}}

    part = parts[config.partno]
    for key in part.keys():
        setattr(config, key, part[key])

def get_config(argv):
    description = 'Upload firmware over the air.'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--partno', '-p',
                        help = 'AVR device.')
    parser.add_argument('--boot_addr', '-b',
                        default = '3e:3e:3e:3e:3e',
                        help = 'Remote boot upload address.')
    parser.add_argument('--info_addr', '-i',
                        default = '3e:3e:3e:3e:24',
                        help = 'Remote device info address.')
    parser.add_argument('filename',
                        help = 'Hex file containing the firmware.')

    config = parser.parse_args(argv)
    get_part_config(config)
    return config

def main(argv = None):
    if argv is None:
        argv = sys.argv[1:]

    config = get_config(argv)

    ser = serial_connect(config)
    get_device_info(config, ser)
    set_address(ser, config.boot_addr)
    (raw_data, crc) = read_data(config)
    send_data(config, ser, raw_data, crc)

if __name__ == "__main__":
    sys.exit(main())
