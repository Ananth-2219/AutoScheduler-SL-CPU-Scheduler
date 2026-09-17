"""
scheduler/srtf.py
-----------------
Shortest Remaining Time First (SRTF) — preemptive scheduler.

At every scheduling decision the ready process with the *smallest*
remaining CPU burst time is chosen.  When a newly arrived process has
a shorter remaining time than the currently running process, the current
process is immediately preempted and returned to the ready queue.

SRTF vs SJF
-----------
SJF  (scheduler/sjf.py) is non-preemptive: once a process is given the
     CPU it runs to completion.  The shortest *total* burst time wins at
     each dispatch point.

SRTF is preemptive: at every new arrival (and at every completion) the
     scheduler re-evaluates and may preempt.  The shortest *remaining*
     burst time wins at each evaluation point.

SRTF generally produces lower average waiting time than SJF but incurs
more context switches and higher overhead.  It does not always perform
better in every metric; for example, a long process that keeps being
preempted accumulates a very high waiting time.

Tie-breaking
------------
When two processes have the same remaining_time the one that *arrived
earlier* wins.  If arrival times are also equal the one with the
lexicographically smaller pid wins.  This makes results fully
deterministic regardless of input order.

CPU idle periods
-----------------
If no process has arrived by the current clock, the clock advances to
the earliest pending arrival before resuming scheduling.
"""

from typing import List, Tuple
import copy

from simulator.process import Process


def srtf(
    processes: List[Process],
) -> Tuple[List[Process], List[Tuple[str, int, int]]]:
    """
    Run the SRTF (Shortest Remaining Time First) scheduling algorithm.

    Parameters
    ----------
    processes : List[Process]
        The set of processes to schedule.  Each process is *copied*
        internally so the originals are not mutated.

    Returns
    -------
    scheduled : List[Process]
        Copies of the input processes with start_time and completion_time
        set, in the order they completed.
    timeline  : List[Tuple[str, int, int]]
        Gantt-chart entries as (pid, start, end) triples.  A process that
        is preempted will have multiple entries, one per contiguous run.
    """
    if not processes:
        return [], []

    procs = copy.deepcopy(processes)

    # Sort by arrival so we can detect new arrivals efficiently.
    pending = sorted(procs, key=lambda p: (p.arrival_time, p.pid))

    timeline: List[Tuple[str, int, int]] = []
    scheduled: List[Process] = []
    ready: List[Process] = []       # processes in the ready queue
    current_time: int = 0
    running: Process | None = None  # currently executing process

    def _admit(until: int) -> None:
        """Move processes from pending to ready if they have arrived by `until`."""
        while pending and pending[0].arrival_time <= until:
            ready.append(pending.pop(0))

    def _pick_next() -> Process:
        """Return the ready process with the smallest remaining_time.
        Tie-break: (remaining_time, arrival_time, pid)."""
        return min(ready, key=lambda p: (p.remaining_time, p.arrival_time, p.pid))

    # Admit any process arriving at time 0.
    _admit(current_time)

    while pending or ready or running is not None:
        # --- CPU idle: no one is ready ---
        if not ready and running is None:
            if not pending:
                break
            current_time = pending[0].arrival_time
            _admit(current_time)

        # --- Choose the next process to run ---
        if ready:
            candidate = _pick_next()
        else:
            # Only the current process is available; it keeps running.
            candidate = running

        # --- Preemption check ---
        if running is not None and running is not candidate:
            # The running process is being preempted.  Do nothing here;
            # the timeline segment will be closed when we switch below.
            pass

        if running is not candidate:
            # Record first-start time for a process receiving the CPU for
            # the first time.
            if candidate.start_time == -1:
                candidate.start_time = current_time
            running = candidate
            if candidate in ready:
                ready.remove(candidate)

        # --- Find the next event time ---
        # The current run segment ends at the earliest of:
        #   a) the running process finishing,
        #   b) the next process arrival (which might trigger preemption).
        run_until = current_time + (running.remaining_time if running else 0)
        next_arrival = pending[0].arrival_time if pending else run_until

        segment_end = min(run_until, next_arrival)

        # Run for (segment_end - current_time) ticks.
        run_ticks = segment_end - current_time
        if run_ticks > 0:
            if timeline and timeline[-1][0] == running.pid and timeline[-1][2] == current_time:
                timeline[-1] = (running.pid, timeline[-1][1], segment_end)
            else:
                timeline.append((running.pid, current_time, segment_end))
            running.remaining_time -= run_ticks
            current_time = segment_end

        # Admit any processes that have arrived at the new current_time.
        _admit(current_time)

        # --- Did the running process finish? ---
        if running is not None and running.remaining_time == 0:
            running.completion_time = current_time
            scheduled.append(running)
            running = None
        else:
            # Running process still has work left; put it back in the
            # ready queue so it competes with newly arrived processes.
            if running is not None:
                ready.append(running)
                running = None

    return scheduled, timeline
