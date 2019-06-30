# Used for SQ2/SQ3 primarily
import argparse
import glob
import importlib
import json
import os
import shutil
import threading

import tmpfile

import wavbintool
import vas3tool
import ifs
import eamxml
import event

import seqtool_main

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-ifs-seq', help='Input file/folder for SEQ (IFS)')
    parser.add_argument('--input-ifs-bgm', help='Input file/folder for BGM (IFS)')
    parser.add_argument('--ifs-target', help="Target specific chart type within IFS", default='sq3', choices=['sq3', 'sq2'])

    parser.add_argument('--output', help='Output file/folder', required=True)
    parser.add_argument('--output-format', help='Output file format', required=True)

    parser.add_argument('--parts', nargs='*', choices=['drum', 'guitar', 'bass', 'open', 'all'], default="all")
    parser.add_argument('--difficulty', nargs='*', choices=['nov', 'bsc', 'adv', 'ext', 'mst', 'all', 'max', 'min'], default="all")

    parser.add_argument('--music-id', type=int, help="Force a music ID", default=None)

    args = parser.parse_args()

    # Clean parts and difficulty
    if 'all' in args.parts:
        args.parts = ['drum', 'guitar', 'bass', 'open']

    if 'all' in args.difficulty:
        args.difficulty = ['nov', 'bsc', 'adv', 'ext', 'mst']
    elif 'min' in args.difficulty:
        args.difficulty = ['min']
    elif 'max' in args.difficulty:
        args.difficulty = ['max']

    if os.path.isdir(args.input_ifs_seq):
        filenames = glob.glob(args.input_ifs_seq + "/*")

    else:
        filenames, _ = ifs.extract(args.input_ifs_seq)

    # Try to match charts with sound files, then extract as required
    guitar = {}
    drum = {}
    for filename in filenames:
        base_filename = os.path.basename(filename)

        target_charts = [".sq3", ".sq2"]
        target_events = [".ev2"]
        if args.ifs_target:
            if args.ifs_target.lower() == "sq2":
                target_charts = [".sq2"]
                target_events = []
            elif args.ifs_target.lower() == "sq3":
                target_charts = [".sq3"]
                target_events = [".ev2"]
            else:
                raise Exception("Invalid IFS target selected")

        if base_filename[-4:] in target_charts:
            if base_filename[0] == 'd':
                drum['seq'] = filename
            elif base_filename[0] == 'g':
                guitar['seq'] = filename
        elif base_filename[-4:] == ".va3":
            if base_filename[-5] == 'd':
                drum['sound'] = filename
            elif base_filename[-5] == 'g':
                guitar['sound'] = filename
        elif base_filename[-4:] in target_events:
            # Give priority to the events file at the top of the list
            if base_filename[-4:] != target_events[0] and 'events' in drum:
                continue

            event_xml = eamxml.get_raw_xml(open(filename, "rb").read())

            if event_xml:
                events = event.get_bonus_notes_by_timestamp(event_xml)
                drum['events'] = events
                guitar['events'] = events

    sound_folder = args.output

    os.makedirs(sound_folder, exist_ok=True)

    if args.input_ifs_bgm:
        if os.path.isdir(args.input_ifs_bgm):
            filenames_bgm = glob.glob(args.input_ifs_bgm + "/*.bin")
        else:
            filenames_bgm, _ = ifs.extract(args.input_ifs_bgm)

        for filename in filenames_bgm:
            # Convert to WAV
            output_filename = filename.replace(".bin", ".wav")
            output_filename = os.path.join(sound_folder, os.path.basename(filename).replace(".bin", ".wav"))

            print("Converting %s..." % output_filename)
            wavbintool.parse_bin(filename, output_filename)
    else:
        filenames_bgm = None

    def handle_set(file_set, game_type):
        if 'seq' not in file_set or not file_set['seq']:
            return

        # Extract va3 files
        if 'sound' in file_set:
            print("Parsing %s..." % file_set['sound'])
            vas3tool.read_vas3(file_set['sound'], sound_folder, force_hex=True, force_game=game_type)

        params = {
            "input": file_set['seq'],
            "input_format": None,
            "output": args.output,
            "output_format": args.output_format,
            "sound_folder": sound_folder,
            "sound_metadata": seqtool_main.get_sound_metadata(sound_folder, game_type),
            "event_file": file_set['event'] if 'event' in file_set else None,
            "parts": args.parts,
            "difficulty": args.difficulty,
            "events": file_set['events'] if 'events' in file_set else {},
            "musicid": args.music_id,
        }

        return params

    if "guitar" in args.parts or "bass" in args.parts or "open" in args.parts:
        seqtool_main.add_task(handle_set(guitar, "guitar"))

    if "drum" in args.parts:
        seqtool_main.add_task(handle_set(drum, "drum"))

    seqtool_main.run_tasks()


if __name__ == "__main__":
    main()
