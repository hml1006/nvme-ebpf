#!/usr/bin/python

from bcc import BPF
from datetime import datetime
from time import sleep
import ctypes

bpf_src = '''
#include<linux/blkdev.h>
#include<linux/nvme.h>
#include<linux/genhd.h>

struct nvme_ns {

};

enum {
	COUNTER = 0,
	LAT_SUM,
	BYTES_SUM,
	MAX_STATS
};

BPF_ARRAY(pread_stats, u64, MAX_STATS);
BPF_HASH(pread_start, u64);
BPF_HISTOGRAM(pread_lat, u64);
BPF_HISTOGRAM(pread_data, u64);

TRACEPOINT_PROBE(syscalls, sys_enter_pread64) {
    u64 tid = bpf_get_current_pid_tgid();
    u32 pid = tid >> 32;
    if (pid != MYSQLD_PID) {
	return 0;
    }
    u64 start = bpf_ktime_get_ns();
    pread_start.update(&tid, &start);
    return 0;
}

TRACEPOINT_PROBE(syscalls, sys_exit_pread64) {
    u64 tid = bpf_get_current_pid_tgid();
    u32 pid = tid >> 32;
    if (pid != MYSQLD_PID) {
	return 0;
    }

    u64 *start = pread_start.lookup(&tid);
    if (start == 0)
	return 0;
    pread_start.delete(&tid);
    u64 usecs = (bpf_ktime_get_ns() - *start) / 1000;
    pread_stats.atomic_increment(COUNTER);
    pread_stats.atomic_increment(LAT_SUM, usecs);
    pread_stats.atomic_increment(BYTES_SUM, args->ret);
    pread_lat.atomic_increment(bpf_log2l(usecs));
    pread_data.atomic_increment(bpf_log2l(args->ret / 1024));
    return 0;
}

struct nvme_key_t {
    char key[DISK_NAME_LEN];
};

BPF_HASH(nvme_start, struct request *);
BPF_HASH(nvme_read_count, struct nvme_key_t);
BPF_HASH(nvme_read_lat, struct nvme_key_t);
BPF_HASH(nvme_read_len, struct nvme_key_t);
BPF_HISTOGRAM(std_nvme_read_lat_hist);
BPF_HISTOGRAM(std_nvme_read_len_hist);
BPF_HISTOGRAM(smi_nvme_read_lat_hist);
BPF_HISTOGRAM(smi_nvme_read_len_hist);

BPF_HASH(nvme_write_count, struct nvme_key_t);
BPF_HASH(nvme_write_lat, struct nvme_key_t);
BPF_HASH(nvme_write_len, struct nvme_key_t);
BPF_HISTOGRAM(std_nvme_write_lat_hist);
BPF_HISTOGRAM(std_nvme_write_len_hist);
BPF_HISTOGRAM(smi_nvme_write_lat_hist);
BPF_HISTOGRAM(smi_nvme_write_len_hist);

int do_nvme_setup_cmd(struct pt_regs *ctx, struct nvme_ns *ns, struct request *req) {
    if (req->rq_disk == NULL) {
	return 0;
    }
    u64 start = bpf_ktime_get_ns();
    nvme_start.update(&req, &start);

    return 0;
}

int do_nvme_complete_rq(struct pt_regs *ctx, struct request *req) {
    if (req->rq_disk == NULL) {
	return 0;
    }

    u64 *start = nvme_start.lookup(&req);
    if (start == 0)
	return 0;
    nvme_start.delete(&req);
    u32 flag = (req->cmd_flags & ((1 << 8) - 1));
    if (flag >= 2) // only record read and write command
	return 0;

    struct nvme_key_t key;
    __builtin_memset(key.key, 0, sizeof(key.key));
    bpf_probe_read_kernel_str(key.key, DISK_NAME_LEN, req->rq_disk->disk_name);
    u64 usecs = (bpf_ktime_get_ns() - *start) / 1000;
    u32 data_len = req->__data_len;

    if (flag == 0) {
	nvme_read_count.atomic_increment(key);
	nvme_read_lat.atomic_increment(key, usecs);
	nvme_read_len.atomic_increment(key, data_len);
	if (req->rq_disk->disk_name[0] == 's') {
		smi_nvme_read_lat_hist.atomic_increment(bpf_log2l(usecs));
		smi_nvme_read_len_hist.atomic_increment(bpf_log2l(data_len / 1024));
	} else {
		std_nvme_read_lat_hist.atomic_increment(bpf_log2l(usecs));
		std_nvme_read_len_hist.atomic_increment(bpf_log2l(data_len / 1024));
	}
    } else {
	nvme_write_count.atomic_increment(key);
	nvme_write_lat.atomic_increment(key, usecs);
	nvme_write_len.atomic_increment(key, data_len);
	if (req->rq_disk->disk_name[0] == 's') {
		smi_nvme_write_lat_hist.atomic_increment(bpf_log2l(usecs));
		smi_nvme_write_len_hist.atomic_increment(bpf_log2l(data_len / 1024));
	} else {
		std_nvme_write_lat_hist.atomic_increment(bpf_log2l(usecs));
		std_nvme_write_len_hist.atomic_increment(bpf_log2l(data_len / 1024));
	}
    }
    
    return 0;
}

BPF_ARRAY(get_stats, u64, MAX_STATS);
BPF_HASH(get_start, u64);
BPF_HISTOGRAM(get_lat, u64);

int do_uprobe_dbimp_get_enter(struct pt_regs *ctx) {
    u64 tid = bpf_get_current_pid_tgid();
    u64 start = bpf_ktime_get_ns();

    get_start.update(&tid, &start);

    return 0;
}

int do_uretprobe_dbimpl_get_exit(struct pt_regs *ctx) {
    u64 tid = bpf_get_current_pid_tgid();
    u64 *start = get_start.lookup(&tid);
    if (start == 0)
	return 0;
    u64 usecs = (bpf_ktime_get_ns() - *start) / 1000;
    get_start.delete(&tid);

    get_stats.atomic_increment(COUNTER);
    get_stats.atomic_increment(LAT_SUM, usecs);
    get_lat.atomic_increment(bpf_log2l(usecs));

    return 0;
}

'''

bpf = None

with open('/var/run/mysqld/mysqld.pid', 'r') as f:
	pid = f.readline()
	if not pid or len(pid) == 0:
		exit(1)
	bpf_src = bpf_src.replace('MYSQLD_PID', pid)
bpf = BPF(text=bpf_src)

bpf.attach_kprobe(event=b'nvme_setup_cmd', fn_name=b'do_nvme_setup_cmd')
bpf.attach_kprobe(event=b'smi_nvme_setup_cmd', fn_name=b'do_nvme_setup_cmd')
bpf.attach_kprobe(event=b'nvme_complete_rq', fn_name=b'do_nvme_complete_rq')
bpf.attach_kprobe(event=b'smi_nvme_complete_rq', fn_name=b'do_nvme_complete_rq')
bpf.attach_uprobe(name=b'/usr/lib64/mysql/plugin/ha_rocksdb.so', sym=b'_ZN7rocksdb6DBImpl7GetImplERKNS_11ReadOptionsERKNS_5SliceERNS0_14GetImplOptionsE', \
	fn_name=b'do_uprobe_dbimp_get_enter')
bpf.attach_uretprobe(name=b'/usr/lib64/mysql/plugin/ha_rocksdb.so', sym=b'_ZN7rocksdb6DBImpl7GetImplERKNS_11ReadOptionsERKNS_5SliceERNS0_14GetImplOptionsE', \
	fn_name=b'do_uretprobe_dbimpl_get_exit')

interval=5

class NvmeKey(ctypes.Structure):
	_fields_ = [('key', ctypes.c_char * 32)]

print('Press Ctl+C to stop')
while True:
	try:
		sleep(interval)
	except KeyboardInterrupt:
		exit()
	pread_stats=bpf['pread_stats']
	pread_lat=bpf['pread_lat']
	pread_data=bpf['pread_data']

	pread_counter=pread_stats[0].value
	pread_lat_sum=pread_stats[1].value
	pread_data_sum=pread_stats[2].value

	avg_lat=0
	avg_data=0
	if pread_counter != 0:
		avg_lat=pread_lat_sum/ pread_counter
		avg_data=pread_data_sum / pread_counter

	print('-------------- %s -------------' % (datetime.now().strftime('%Y-%m-%d, %H:%M:%S')))
	print('__________________pread____________________')
	print('count: %d, latency total: %d us, latency avg: %d us, bytes total: %d MB, bytes avg: %d KB' % \
		(pread_counter, pread_lat_sum, avg_lat, pread_data_sum / (1024 * 1024), avg_data / 1024))
	pread_stats.clear()
	print('')
	pread_lat.print_log2_hist('latency/us')
	pread_lat.clear()
	print('')
	pread_data.print_log2_hist('read/KB')
	pread_data.clear()

	nvme_read_count_stats=bpf['nvme_read_count']
	nvme_read_lat_stats=bpf['nvme_read_lat']
	nvme_read_len_stats=bpf['nvme_read_len']
	std_nvme_read_lat_hist=bpf['std_nvme_read_lat_hist']
	std_nvme_read_len_hist=bpf['std_nvme_read_len_hist']
	smi_nvme_read_lat_hist=bpf['smi_nvme_read_lat_hist']
	smi_nvme_read_len_hist=bpf['smi_nvme_read_len_hist']

	nvme_write_count_stats=bpf['nvme_write_count']
	nvme_write_lat_stats=bpf['nvme_write_lat']
	nvme_write_len_stats=bpf['nvme_write_len']
	std_nvme_write_lat_hist=bpf['std_nvme_write_lat_hist']
	std_nvme_write_len_hist=bpf['std_nvme_write_len_hist']
	smi_nvme_write_lat_hist=bpf['smi_nvme_write_lat_hist']
	smi_nvme_write_len_hist=bpf['smi_nvme_write_len_hist']

	print('____________________nvme_____________________')

	# dev
	nvme0n1 = NvmeKey()
	nvme0n1.key = 'nvme0n1'.encode()
	smi_nvme0n1 = NvmeKey()
	smi_nvme0n1.key = 'smi_nvme0n1'.encode()
	# read
	for dev in [nvme0n1, smi_nvme0n1]:
		if dev not in nvme_read_count_stats:
			continue
		nvme_read_count=nvme_read_count_stats[dev].value
		if nvme_read_count <= 0:
			continue
		nvme_read_lat_sum=nvme_read_lat_stats[dev].value
		nvme_bytes_sum=nvme_read_len_stats[dev].value
		nvme_read_lat_avg=0
		nvme_bytes_avg=0

		if nvme_read_count != 0:
			nvme_read_lat_avg=nvme_read_lat_sum / nvme_read_count
			nvme_bytes_avg=nvme_bytes_sum / nvme_read_count
			print('%s read ======> count: %d, latency total: %d us, latency avg: %d us, bytes total: %d MB, bytes avg: %d KB\n' % 
				(dev.key, nvme_read_count, nvme_read_lat_sum, nvme_read_lat_avg, nvme_bytes_sum / (1024 * 1024), nvme_bytes_avg / 1024))
			if dev.key == 'nvme0n1':
				std_nvme_read_lat_hist.print_log2_hist('latency/us')
				print('')
				std_nvme_read_len_hist.print_log2_hist('read/KB')
				print('')
			elif dev.key == 'smi_nvme0n1':
				smi_nvme_read_lat_hist.print_log2_hist('latency/us')
				print('')
				smi_nvme_read_len_hist.print_log2_hist('read/KB')
				print('')
	# write
	for dev in [nvme0n1, smi_nvme0n1]:
		if dev not in nvme_write_count_stats:
			continue
		nvme_write_count=nvme_write_count_stats[dev].value
		if nvme_write_count <= 0:
			continue
		nvme_write_lat_sum=nvme_write_lat_stats[dev].value
		nvme_bytes_sum=nvme_write_len_stats[dev].value
		nvme_write_lat_avg=0
		nvme_bytes_avg=0

		if nvme_write_count != 0:
			nvme_write_lat_avg=nvme_write_lat_sum / nvme_write_count
			nvme_bytes_avg=nvme_bytes_sum / nvme_write_count
			print('%s write ======> count: %d, latency total: %d us, latency avg: %d us, bytes total: %d MB, bytes avg: %d KB\n' % 
				(dev.key, nvme_write_count, nvme_write_lat_sum, nvme_write_lat_avg, nvme_bytes_sum / (1024 * 1024), nvme_bytes_avg / 1024))
			if dev.key == 'nvme0n1':
				std_nvme_write_lat_hist.print_log2_hist('latency/us')
				print('')
				std_nvme_write_len_hist.print_log2_hist('write/KB')
				print('')
			elif dev.key == 'smi_nvme0n1':
				smi_nvme_write_lat_hist.print_log2_hist('latency/us')
				print('')
				smi_nvme_write_len_hist.print_log2_hist('write/KB')
				print('')
	std_nvme_read_lat_hist.clear()
	std_nvme_read_len_hist.clear()
	smi_nvme_read_lat_hist.clear()
	smi_nvme_read_len_hist.clear()
	nvme_read_count_stats.clear()
	nvme_read_lat_stats.clear()
	nvme_read_len_stats.clear()

	std_nvme_write_lat_hist.clear()
	std_nvme_write_len_hist.clear()
	smi_nvme_write_lat_hist.clear()
	smi_nvme_write_len_hist.clear()
	nvme_write_count_stats.clear()
	nvme_write_lat_stats.clear()
	nvme_write_len_stats.clear()

	get_stats=bpf['get_stats']
	get_lat=bpf['get_lat']

	get_count=get_stats[0].value
	get_lat_sum=get_stats[1].value
	get_lat_avg=0
	if get_count > 0:
		get_lat_avg=get_lat_sum / get_count
	get_stats.clear()
	print('____________________get_________________')
	print('count: %d, latency total: %d us, latency avg: %d us\n' % (get_count, get_lat_sum, get_lat_avg))
	get_lat.print_log2_hist('latency/us')
	get_lat.clear()