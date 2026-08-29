#!/usr/bin/env bash

set -uo pipefail

if [[ $# -ne 6 ]]; then
	echo "usage: $0 <workers> <manifest> <output-root> <content-dir> <engine-dir> <evidence-root>" >&2
	exit 2
fi

workers=$1
manifest=$2
output_root=$3
content_dir=$4
engine_dir=$5
evidence_root=$6
samples="$evidence_root/resource-samples-workers-$workers.csv"

mkdir -p "$output_root" "$evidence_root"
echo 'unix_ms,mem_available_bytes,swap_used_bytes,load_1m,openra_processes,openra_rss_kib,disk_available_bytes' > "$samples"

memory_events=''
: > "$evidence_root/memory-events-before-workers-$workers.txt"
: > "$evidence_root/memory-events-after-workers-$workers.txt"
if [[ -r /sys/fs/cgroup/memory.events ]]; then
	memory_events=/sys/fs/cgroup/memory.events
else
	relative=$(awk -F: '$1 == "0" { print $3; exit }' /proc/self/cgroup)
	if [[ -n "$relative" && -r "/sys/fs/cgroup$relative/memory.events" ]]; then
		memory_events="/sys/fs/cgroup$relative/memory.events"
	fi
fi

if [[ -n "$memory_events" ]]; then
	cp "$memory_events" "$evidence_root/memory-events-before-workers-$workers.txt"
fi

set +e
/usr/bin/time -v -o "$evidence_root/workers-$workers-time.txt" \
	xvfb-run -a -s "-screen 0 1024x768x24" \
		python3 tools/strategic_ai_runner.py run \
			--manifest "$manifest" \
			--output-root "$output_root" \
			--content-dir "$content_dir" \
			--engine-dir "$engine_dir" \
			--max-workers "$workers" \
			--skip-build &
controller_pid=$!

while kill -0 "$controller_pid" 2>/dev/null; do
	unix_ms=$(date +%s%3N)
	mem_kib=$(awk '/^MemAvailable:/ { print $2 }' /proc/meminfo)
	swap_used_kib=$(awk '
		/^SwapTotal:/ { total = $2 }
		/^SwapFree:/ { free = $2 }
		END { print total - free }
	' /proc/meminfo)
	load_1m=$(awk '{ print $1 }' /proc/loadavg)
	read -r process_count rss_kib < <(
		ps -eo rss=,args= | awk '/\/bin\/OpenRA( |$)/ { count += 1; rss += $1 } END { print count + 0, rss + 0 }'
	)
	disk_bytes=$(df -B1 --output=avail "$RUNNER_TEMP" | tail -n 1 | tr -d ' ')
	echo "$unix_ms,$((mem_kib * 1024)),$((swap_used_kib * 1024)),$load_1m,$process_count,$rss_kib,$disk_bytes" >> "$samples"
	sleep 0.2
done

wait "$controller_pid"
controller_exit=$?
set -e
echo "$controller_exit" > "$evidence_root/controller-exit-code-workers-$workers.txt"
if [[ -n "$memory_events" ]]; then
	cp "$memory_events" "$evidence_root/memory-events-after-workers-$workers.txt"
fi

# Return success so the workflow can always upload the recorded evidence.
# The calling workflow propagates the recorded controller exit afterward.
exit 0
