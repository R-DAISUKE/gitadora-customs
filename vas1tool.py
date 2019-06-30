# TODO: Remove unneeded code
# TODO: Add support for audio metadata
# TODO: Figure out differences between GF and DM VAS archives

import argparse
import io
import json
import math
import numpy
import os
import pydub
import struct
import sys
import wavfile
import pydub

import audio
import tmpfile
import helper

FLAG_MAP = {
    "DefaultSound": 0x04,
    "NoFilename": 0x0100
}

def read_vas1(input_filename, input_fre_filename, output_folder, force_hex=False, mix_audio=False, is_guitar=False):
    data = open(input_filename, "rb").read()

    entry_count = struct.unpack("<I", data[0x00:0x04])[0]
    entry_start = 0x04

    if entry_count <= 0:
        print("No files to extract")
        exit(1)

    default_leftcymbal = 0xfff0
    default_floortom = 0xfff1
    default_leftpedal = 0xfff2

    if input_fre_filename:
        fre_data = open(input_fre_filename, "rb").read()

        if len(fre_data) == 12:
            default_hihat = int.from_bytes(fre_data[0:2], byteorder="little")
            default_snare = int.from_bytes(fre_data[2:4], byteorder="little")
            default_bass = int.from_bytes(fre_data[4:6], byteorder="little")
            default_hightom = int.from_bytes(fre_data[6:8], byteorder="little")
            default_lowtom = int.from_bytes(fre_data[8:10], byteorder="little")
            default_rightcymbal = int.from_bytes(fre_data[10:12], byteorder="little")

        else:
            search_filename = os.path.splitext(os.path.basename(input_filename))[0].lower()
            found_fre = False

            for i in range(len(fre_data) // 0x18):
                filename = fre_data[i*0x18:i*0x18+12].decode('ascii').strip('\0')

                if filename == search_filename:
                    cur_fre_data = fre_data[i*0x18+12:(i+1)*0x18]
                    default_hihat = int.from_bytes(cur_fre_data[0:2], byteorder="little")
                    default_snare = int.from_bytes(cur_fre_data[2:4], byteorder="little")
                    default_bass = int.from_bytes(cur_fre_data[4:6], byteorder="little")
                    default_hightom = int.from_bytes(cur_fre_data[6:8], byteorder="little")
                    default_lowtom = int.from_bytes(cur_fre_data[8:10], byteorder="little")
                    default_rightcymbal = int.from_bytes(cur_fre_data[10:12], byteorder="little")
                    found_fre = True

                    break

            if not found_fre:
                print("Couldn't find default keysound entries for", input_filename)
                exit(1)

    else:
        default_hihat = 0
        default_snare = 0
        default_bass = 0
        default_hightom = 0
        default_lowtom = 0
        default_rightcymbal = 0

    entries = []
    for i in range(entry_count):
        # sound_flag seems to be related to defaults. If something is set to default, it is 0x02. Else it's 0x04 (for GDXG). Always 0 for GDXH?
        # entry_unk4 seems to always be 255??
        metadata_offset, offset, filesize = struct.unpack("<III", data[entry_start+(i*0x0c):entry_start+(i*0x0c)+0x0c])
        metadata_unk1_1, volume, pan, sound_id, instrument_id, metadata_unk2_2, metadata_unk2_3, metadata_unk2_4, metadata_unk3, sample_rate = struct.unpack("<BBBBBBBBHH", data[entry_start+metadata_offset+(entry_count*0x0c):entry_start+metadata_offset+(entry_count*0x0c)+0x0c])
        # sample_rate *= 3
        sample_rate = 22050

        #output_filename = os.path.join(basepath, "{}.wav".format(entry['filename']))

        print("%04x | %08x %08x %08x | %02x %02x %02x %02x  %02x %02x %02x %02x  %04x  %04x | %08x | %08x %d" % (i, metadata_offset, offset, filesize, metadata_unk1_1, volume, pan, sound_id, instrument_id, metadata_unk2_2, metadata_unk2_3, metadata_unk2_4, sample_rate, metadata_unk3, entry_start+metadata_offset+(entry_count*0x0c), sample_rate, sample_rate))

        offset += ((entry_count * 0x0c) * 2) + 4

        entries.append((offset, filesize, i, volume, pan + 64 if is_guitar else pan - 100))

    entries.append(len(data))

    if output_folder:
        basepath = output_folder
    else:
        basepath = os.path.splitext(os.path.basename(input_filename))[0]

    os.makedirs(basepath, exist_ok=True)

    metadata = {
        'type': "GDXG" if is_guitar else "GDXH",
        'version': 1,
        'defaults': {
            'default_hihat': default_hihat,
            'default_snare': default_snare,
            'default_bass': default_bass,
            'default_hightom': default_hightom,
            'default_lowtom': default_lowtom,
            'default_rightcymbal': default_rightcymbal,
            'default_leftcymbal': default_leftcymbal,
            'default_floortom': default_floortom,
            'default_leftpedal': default_leftpedal,
        },
        'gdx_type_unk1': 0,
        'gdx_volume_flag': 1,
        'entries': [],
    }

    for idx, entry_info in enumerate(entries[:-1]):
        entry, filesize, sound_id, volume, pan = entry_info
        #filesize = entries[idx + 1] - entry

        output_filename = os.path.join(basepath, "%04x.pcm" % (idx))

        print("Extracting %s | %d %d %d" % (output_filename, sound_id, volume, pan))
        with open(output_filename, "wb") as outfile:
            outfile.write(struct.pack(">IHHB", filesize, 0, sample_rate if is_guitar else 44100, 1))
            outfile.write(bytearray([0] * 7))
            outfile.write(bytearray([0] * 0x800))
            outfile.write(data[entry:entry+filesize])

        audio.get_wav_from_pcm(output_filename)
        os.remove(output_filename)

        entry_filename = "%s.%04d" % (os.path.basename(os.path.splitext(input_filename)[0]).lower(), sound_id)

        duration = len(pydub.AudioSegment.from_file(os.path.splitext(output_filename)[0] + ".wav")) / 1000

        metadata['entries'].append({
            'sound_id': sound_id,
            'filename': entry_filename,
            'volume': volume,
            'pan': pan,
            'extra': 255, # Unknown
            'flags': ['NoFilename'],
            'duration': duration,
        })

    open(os.path.join(basepath, "metadata.json"), "w").write(json.dumps(metadata, indent=4))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', help='Input file', required=True)
    parser.add_argument('-r', '--input-fre', help='Input FRE file', default=None)
    parser.add_argument('-o', '--output', help='Output file', required=True)
    parser.add_argument('-m', '--mix', action='store_true', help='Mix output files using volume and pan parameters', required=False, default=False)
    parser.add_argument('-g', '--guitar', action='store_true', help='Is extracting guitar archive', required=False, default=False)
    parser.add_argument('-f', '--force-hex', action='store_true', help='Force hex filenames', required=False, default=False)
    args = parser.parse_args()

    if not args.guitar and not args.input_fre:
        print("Must specify an input FRE file with drum data")
        exit(1)

    read_vas1(args.input, args.input_fre, args.output, args.force_hex, args.mix, args.guitar)
