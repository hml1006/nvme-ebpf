#!/usr/bin/python3

import re
import argparse
import collections

# current parse state
new_second = 0
usecs_stats_read = 1
usecs_stats_write = 2
usecs_read = 3
usecs_write = 4
data_stats_read = 5
data_stats_write = 6
data_read = 7
data_write = 8

items_parse = 99
invalid = 100

current_line = None
current_file = None
current_time = None

usecs_stats_read_count = collections.OrderedDict()
usecs_stats_write_count = collections.OrderedDict()
usecs_stats_read_avg = collections.OrderedDict()
usecs_stats_write_avg = collections.OrderedDict()
usecs_read_list = collections.OrderedDict()
usecs_write_list = collections.OrderedDict()
data_stats_read_avg = collections.OrderedDict()
data_stats_write_avg = collections.OrderedDict()
data_read_list = collections.OrderedDict()
data_write_list = collections.OrderedDict()

def output_file():
	print('output file')
	usecs_stats_read_count_file = open('usecs_stats_read_count.txt', 'w')
	for k, v in usecs_stats_read_count.items():
		print('%s,%s' % (k, v), file=usecs_stats_read_count_file)
	usecs_stats_write_count_file = open('usecs_stats_write_count.txt', 'w')
	for k, v in usecs_stats_write_count.items():
		print('%s,%s' % (k, v), file=usecs_stats_write_count_file)
	usecs_stats_read_avg_file = open('usecs_stats_read_avg.txt', 'w')
	for k, v in usecs_stats_read_avg.items():
		print('%s,%s' % (k, v), file=usecs_stats_read_avg_file)
	usecs_stats_write_avg_file = open('usecs_stats_write_avg.txt', 'w')
	for k, v in usecs_stats_write_avg.items():
		print('%s,%s' % (k, v), file=usecs_stats_write_avg_file)
	data_stats_read_avg_file = open('data_stats_read_avg.txt', 'w')
	for k, v in data_stats_read_avg.items():
		print('%s,%s' % (k, v), file=data_stats_read_avg_file)
	data_stats_write_avg_file = open('data_stats_write_avg.txt', 'w')
	for k, v in data_stats_write_avg.items():
		print('%s,%s' % (k, v), file=data_stats_write_avg_file)
	usecs_read_list_files = collections.OrderedDict()
	for time, item in usecs_read_list.items():
		for latency, count in item.items():
			line = '%s,%s\n' % (time, count)
			if 'usecs_read_list-' + latency + '.txt' not in usecs_read_list_files:
				usecs_read_list_files['usecs_read_list-' + latency + '.txt'] = ''
			usecs_read_list_files['usecs_read_list-' + latency + '.txt'] = usecs_read_list_files['usecs_read_list-' + latency + '.txt'] + line
	for file, content in usecs_read_list_files.items():
		f = open(file, 'w')
		print(content, file=f)
	usecs_write_list_files = collections.OrderedDict()
	for time, item in usecs_write_list.items():
		for latency, count in item.items():
			line = '%s,%s\n' % (time, count)
			if 'usecs_write_list-' + latency + '.txt' not in usecs_write_list_files:
				usecs_write_list_files['usecs_write_list-' + latency + '.txt'] = ''
			usecs_write_list_files['usecs_write_list-' + latency + '.txt'] = usecs_write_list_files['usecs_write_list-' + latency + '.txt'] + line
	for file, content in usecs_write_list_files.items():
		f = open(file, 'w')
		print(content, file=f)
	data_read_list_files = collections.OrderedDict()
	for time, item in usecs_read_list.items():
		for latency, count in item.items():
			line = '%s,%s\n' % (time, count)
			if 'data_read_list-' + latency + '.txt' not in data_read_list_files:
				data_read_list_files['data_read_list-' + latency + '.txt'] = ''
			data_read_list_files['data_read_list-' + latency + '.txt'] = data_read_list_files['data_read_list-' + latency + '.txt'] + line
	for file, content in data_read_list_files.items():
		f = open(file, 'w')
		print('%s', content, file=f)
	data_write_list_files = collections.OrderedDict()
	for time, item in data_write_list.items():
		for latency, count in item.items():
			line = '%s,%s\n' % (time, count)
			if 'data_write_list-' + latency + '.txt' not in data_write_list_files:
				data_write_list_files['data_write_list-' + latency + '.txt'] = ''
			data_write_list_files['data_write_list-' + latency + '.txt'] = data_write_list_files['data_write_list-' + latency + '.txt'] + line
	for file, content in data_write_list_files.items():
		f = open(file, 'w')
		print(content, file=f)

def check_mode(line, devname):
	if line.startswith('======= '):
		return new_second
	if line.startswith('@usecs_stats[' + devname +', nvme_cmd_read]'):
		return usecs_stats_read
	if line.startswith('@usecs_stats[' + devname +', nvme_cmd_write]'):
		return usecs_stats_write
	if line.startswith('@usecs[' + devname +', nvme_cmd_read]'):
		return usecs_read
	if line.startswith('@usecs[' + devname +', nvme_cmd_write]'):
		return usecs_write
	if line.startswith('@data_stats[' + devname +', nvme_cmd_read]'):
		return data_stats_read
	if line.startswith('@data_stats[' + devname +', nvme_cmd_write]'):
		return data_stats_write
	if line.startswith('@data[' + devname +', nvme_cmd_read]'):
		return data_read
	if line.startswith('@data[' + devname +', nvme_cmd_write]'):
		return data_write
	if line.startswith('['):
		return items_parse
	return invalid

def parse_usecs_stats_read(devname):
	global usecs_stats_read_count
	global usecs_stats_read_avg
	global current_time
	global current_file
	global current_line

	print('parse_usecs_stats_read')
	results = re.search( r'count (\d+), average (\d+),', current_line, re.M|re.I)
	usecs_stats_read_count[current_time] = results.group(1)
	usecs_stats_read_avg[current_time] = results.group(2)

def parse_usecs_stats_write(devname):
	global usecs_stats_write_count
	global usecs_stats_write_avg
	global current_time
	global current_file
	global current_line

	print('parse_usecs_stats_write')
	results = re.search( r'count (\d+), average (\d+),', current_line, re.M|re.I)
	usecs_stats_write_count[current_time] = results.group(1)
	usecs_stats_write_avg[current_time] = results.group(2)

def new_usecs_dict():
	temp = collections.OrderedDict()
	temp['[0-2)'] = 0
	temp['[2-4)'] = 0
	temp['[4-8)'] = 0
	temp['[8-16)'] = 0
	temp['[16-32)'] = 0
	temp['[32-64)'] = 0
	temp['[64-128)'] = 0
	temp['[128-256)'] = 0
	temp['[256-512)'] = 0
	temp['[512-1K)'] = 0
	temp['[1K-2K)'] = 0
	temp['[2K-4K)'] = 0
	temp['[4K-8K)'] = 0
	temp['[8K-16K)'] = 0
	return temp

def parse_usecs_read(devname):
	global current_time
	global current_file
	global current_line
	global usecs_read_list

	print('parse_usecs_read')
	temp = new_usecs_dict()

	while True:
		current_line = current_file.readline()
		if not current_file:
			break
		if check_mode(current_line, devname) == items_parse:
			g1 = None
			g2 = None
			result = re.match(r'\[(\d+)\,\s+\S+\s+(\d+)\s+', current_line, re.M|re.I)
			if result:
				g1 = result.group(1)
				g2 = int(result.group(2))
			else:
				result = re.match(r'\[(\d+K)\,\s+\S+\s+(\d+)\s+', current_line, re.M|re.I)
				if result:
					g1 = result.group(1)
					g2 = int(result.group(2))
			if g1 and g2:
				if g1 == '0':
					temp['[0-2)'] = g2
				elif g1 == '2':
					temp['[2-4)'] = g2
				elif g1 == '4':
					temp['[4-8)'] = g2
				elif g1 == '8':
					temp['[8-16)'] = g2
				elif g1 == '16':
					temp['[16-32)'] = g2
				elif g1 == '32':
					temp['[32-64)'] = g2
				elif g1 == '64':
					temp['[64-128)'] = g2
				elif g1 == '128':
					temp['[128-256)'] = g2
				elif g1 == '256':
					temp['[256-512)'] = g2
				elif g1 == '512':
					temp['[512-1K)'] = g2
				elif g1 == '1K':
					temp['[1K-2K)'] = g2
				elif g1 == '2K':
					temp['[2K-4K)'] = g2
				elif g1 == '4K':
					temp['[4K-8K)'] = g2
				elif g1 == '8K':
					temp['[8K-16K)'] = g2
		else:
			break
	usecs_read_list[current_time] = temp

def parse_usecs_write(devname):
	global current_time
	global current_file
	global current_line
	global usecs_write_list

	print('parse_usecs_write')
	temp = new_usecs_dict()

	while True:
		current_line = current_file.readline()
		if not current_file:
			break
		if check_mode(current_line, devname) == items_parse:
			g1 = None
			g2 = None
			result = re.match(r'\[(\d+)\,\s+\S+\s+(\d+)\s+', current_line, re.M|re.I)
			if result:
				g1 = result.group(1)
				g2 = int(result.group(2))
			else:
				result = re.match(r'\[(\d+K)\,\s+\S+\s+(\d+)\s+', current_line, re.M|re.I)
				if result:
					g1 = result.group(1)
					g2 = int(result.group(2))
			if g1 and g2:
				if g1 == '0':
					temp['[0-2)'] = g2
				elif g1 == '2':
					temp['[2-4)'] = g2
				elif g1 == '4':
					temp['[4-8)'] = g2
				elif g1 == '8':
					temp['[8-16)'] = g2
				elif g1 == '16':
					temp['[16-32)'] = g2
				elif g1 == '32':
					temp['[32-64)'] = g2
				elif g1 == '64':
					temp['[64-128)'] = g2
				elif g1 == '128':
					temp['[128-256)'] = g2
				elif g1 == '256':
					temp['[256-512)'] = g2
				elif g1 == '512':
					temp['[512-1K)'] = g2
				elif g1 == '1K':
					temp['[1K-2K)'] = g2
				elif g1 == '2K':
					temp['[2K-4K)'] = g2
				elif g1 == '4K':
					temp['[4K-8K)'] = g2
				elif g1 == '8K':
					temp['[8K-16K)'] = g2
		else:
			break
	usecs_write_list[current_time] = temp

def parse_data_stats_read(devname):
	global data_stats_read_avg
	global current_time
	global current_file
	global current_line

	print('parse_data_stats_read')
	results = re.search( r'count (\d+), average (\d+),', current_line, re.M|re.I)
	data_stats_read_avg[current_line] = results.group(2)

def parse_data_stats_write(devname):
	global data_stats_write_avg
	global current_time
	global current_file
	global current_line

	print('parse_data_stats_write')
	results = re.search( r'count (\d+), average (\d+),', current_line, re.M|re.I)
	data_stats_write_avg[current_line] = results.group(2)

def new_data_dict():
	temp = collections.OrderedDict()
	temp['[0-16K)'] = 0
	temp['[16K-32K)'] = 0
	temp['[32K-48K)'] = 0
	temp['[48K-64K)'] = 0
	temp['[64K-80K)'] = 0
	temp['[80K-96K)'] = 0
	temp['[96K-112K)'] = 0
	temp['[112K-128K)'] = 0
	temp['[128K-144K)'] = 0

	return temp

def parse_data_read(devname):
	global current_time
	global current_file
	global current_line
	global data_read_list

	print('parse_data_read')
	temp = new_usecs_dict()

	while True:
		current_line = current_file.readline()
		if not current_file:
			break
		if check_mode(current_line, devname) == items_parse:
			g1 = None
			g2 = None
			result = re.match(r'\[.*\,\s+(\d+K)\S+\s+(\d+)\s+', current_line, re.M|re.I)
			if result:
				g1 = result.group(1)
				g2 = int(result.group(2))
			
			if g1 and g2:
				if g1 == '16K':
					temp['[0-16K)'] = g2
				elif g1 == '32K':
					temp['[16K-32K)'] = g2
				elif g1 == '48K':
					temp['[32K-48K)'] = g2
				elif g1 == '64K':
					temp['[48K-64K)'] = g2
				elif g1 == '80K':
					temp['[64K-80K)'] = g2
				elif g1 == '96K':
					temp['[80K-96K)'] = g2
				elif g1 == '112K':
					temp['[96K-112K)'] = g2
				elif g1 == '128K':
					temp['[112K-128K)'] = g2
				elif g1 == '144K':
					temp['[128K-144K)'] = g2
		else:
			break
	data_read_list[current_time] = temp

def parse_data_write(devname):
	global current_time
	global current_file
	global current_line
	global data_write_list

	print('parse_data_write')
	temp = new_usecs_dict()

	while True:
		current_line = current_file.readline()
		if not current_file:
			break
		if check_mode(current_line, devname) == items_parse:
			g1 = None
			g2 = None
			result = re.match(r'\[.*\,\s+(\d+K)\S+\s+(\d+)\s+', current_line, re.M|re.I)
			if result:
				g1 = result.group(1)
				g2 = int(result.group(2))
			
			if g1 and g2:
				if g1 == '16K':
					temp['[0-16K)'] = g2
				elif g1 == '32K':
					temp['[16K-32K)'] = g2
				elif g1 == '48K':
					temp['[32K-48K)'] = g2
				elif g1 == '64K':
					temp['[48K-64K)'] = g2
				elif g1 == '80K':
					temp['[64K-80K)'] = g2
				elif g1 == '96K':
					temp['[80K-96K)'] = g2
				elif g1 == '112K':
					temp['[96K-112K)'] = g2
				elif g1 == '128K':
					temp['[112K-128K)'] = g2
				elif g1 == '144K':
					temp['[128K-144K)'] = g2
		else:
			break
	data_write_list[current_time] = temp

def parse_new_second(devname):
	global current_file
	global current_line
	global current_time

	current_time =  current_line.replace('=', '').strip()
	while True:
		current_line = current_file.readline()
		if not current_line:
			break
		if check_mode(current_line, devname) == usecs_stats_read:
			parse_usecs_stats_read(devname)
		elif check_mode(current_line, devname) == usecs_stats_write:
			parse_usecs_stats_write(devname)
		elif check_mode(current_line, devname) == usecs_read:
			parse_usecs_read(devname)
		elif check_mode(current_line, devname) == usecs_write:
			parse_usecs_write(devname)
		elif check_mode(current_line, devname) == data_stats_read:
			parse_data_stats_read(devname)
		elif check_mode(current_line, devname) == data_stats_write:
			parse_data_stats_write(devname)
		elif check_mode(current_line, devname) == data_read:
			parse_data_read(devname)
		elif check_mode(current_line, devname) == data_write:
			parse_data_write(devname)
		elif check_mode(current_line, devname) == new_second:
			break
		else:
			continue

def parse_file(path, devname):
	global current_file
	global current_line

	with open(path, 'r') as f:
		current_file = f
		current_line = current_file.readline()
		while True:
			if not current_line:
				break
			if check_mode(current_line, devname) == new_second:
				parse_new_second(devname)
			else:
				current_line = current_file.readline()
		output_file()

if __name__ == '__main__':
	parser = argparse.ArgumentParser();
	parser.add_argument('--dev', help='Block dev name, ex: smi_nvme0n1', required=True)
	parser.add_argument('--file', help='Statistic file path', required=True)
	args = parser.parse_args()
	devname = args.dev
	filepath = args.file
	print('dev: %s， file: %s' % (devname, filepath))

	parse_file(filepath, devname)

