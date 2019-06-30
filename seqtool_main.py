import argparse
import copy
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

import plugins


running_threads = []


def find_handler(input_filename, input_format):
    formats = [importlib.import_module('plugins.' + name).get_class() for name in plugins.__all__]

    for handler in formats:
        if not handler:
            continue

        try:
            if input_format is not None and handler.get_format_name().lower() == input_format.lower():
                return handler
            elif input_filename is not None and handler.is_format(input_filename):
                return handler
        except:
            pass

    return None


def filter_charts(json_data, params):
    json_data = json.loads(json_data)

    if 'charts' not in json_data:
        return json_data

    min_diff = None
    max_diff = None
    for chart in json_data['charts']:
        if min_diff == None or chart['header']['difficulty'] < min_diff:
            min_diff = chart['header']['difficulty']

        if max_diff == None or chart['header']['difficulty'] > max_diff:
            max_diff = chart['header']['difficulty']

    filtered_charts = []
    for chart in json_data['charts']:
        if chart['header']['is_metadata'] != 0:
            continue

        part = ["drum", "guitar", "bass", "open"][chart['header']['game_type']]
        has_all = 'all' in params['parts']
        has_part = part in params['parts']

        if not has_all and not has_part:
            filtered_charts.append(chart)
            continue

        diff = ["nov", "bsc", "adv", "ext", "mst"][chart['header']['difficulty']]
        has_min = 'min' in params['difficulty'] and chart['header']['difficulty'] == min_diff
        has_max = 'max' in params['difficulty'] and chart['header']['difficulty'] == max_diff
        has_all = 'all' in params['difficulty']
        has_diff = diff in params['difficulty']

        if not has_min and not has_max and not has_all and not has_diff:
            filtered_charts.append(chart)
            continue

    for chart in filtered_charts:
        json_data['charts'].remove(chart)

    return json.dumps(json_data, indent=4)


def process_file(params):
    input = params['input'] if 'input' in params else None
    input_format = params['input_format'] if 'input_format' in params else None
    output_format = params['output_format'] if 'output_format' in params else None

    if output_format == "same":
        output_format = input_format

    input_handler = find_handler(input, input_format)
    output_handler = find_handler(None, output_format)

    if output_handler is None:
        output_handler = input_handler

    if input_handler is None:
        print("Could not find a handler for input file")
        exit(1)

    if output_handler is None:
        print("Could not find a handler for output file")
        exit(1)

    print("Using {} handler to process this file...".format(input_handler.get_format_name()))

    json_data = input_handler.to_json(params)

    # Filter based on difficulty and parts here
    # json_data = filter_charts(json_data, params)

    if output_format.lower() != 'wav' and 'output' in params and not os.path.exists(params['output']):
        os.makedirs(params['output'])

    params['input'] = json_data
    output_handler.to_chart(params)


def get_sound_metadata(sound_folder, game_type=None):
    if not sound_folder:
        return None

    if game_type == "drum":
        metadata_filename = "d_metadata.json"

    elif game_type == "guitar":
        metadata_filename = "g_metadata.json"

    else:
        metadata_filename = "metadata.json"

    sound_metadata_filename = os.path.join(sound_folder, metadata_filename)

    if os.path.exists(sound_metadata_filename):
        with open(sound_metadata_filename, "r") as f:
            return json.loads(f.read())

    return None


def add_task(params):
    parse_thread = threading.Thread(target=process_file, args=(params,))
    parse_thread.start()
    running_threads.append(parse_thread)


def run_tasks():
    for thread in running_threads:
        thread.join()

    tmpfile.tmpcleanup()
