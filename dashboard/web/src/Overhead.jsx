import React from 'react';
import { Metric, number, Source } from './ui.jsx';
import './overhead.css';

const percentage = value => value == null ? 'Unavailable' : `${number(value, 4)}%`;

function TimingMetrics({timing}) {
  const completionMs = timing.ms_per_tick == null ? null : timing.makespan_ticks * timing.ms_per_tick;
  return <>
    <div className="metric-grid overhead-metrics">
      <Metric label="Total controller overhead" value={number(timing.controller_total_ms, 3)} unit="ms"/>
      <Metric label="Mean decision overhead" value={number(timing.decision_mean_us, 3)} unit="µs"/>
      <Metric label="Decision P99 overhead" value={number(timing.decision_p99_us, 3)} unit="µs"/>
      <Metric label="Overhead / completion time" value={percentage(timing.controller_vs_makespan_percent)}
        note={completionMs == null ? 'Ticks have no defined millisecond scale.' : `${number(completionMs, 3)} ms total simulated makespan, including idle time`}/>
      <Metric label="Overhead / Python replay time" value={percentage(timing.controller_share_python_wall_percent)}
        note={`${number(timing.python_simulation_wall_ms, 3)} ms measured Python replay time`}/>
    </div>
    <p className="subtle">{number(timing.reviews, 0)} timed controller reviews · {number(timing.accepted_switches, 0)} accepted transitions.
      {timing.ms_per_tick != null && <> Overhead / CPU-demand proxy: <strong>{percentage(timing.controller_vs_cpu_proxy_percent)}</strong> ({number(timing.cpu_proxy_ticks * timing.ms_per_tick, 3)} ms CPU work, excluding idle time).</>}
    </p>
  </>;
}

export function CohortOverhead({snapshot, cohortId}) {
  const cohort = snapshot?.cohorts?.[cohortId];
  if (!cohort) return <div className="controller-overhead"><h3>Controller Overhead</h3><p>{snapshot?.reason || 'Matching workload timing has not been recorded.'}</p></div>;
  return <div className="controller-overhead" aria-label={`Controller overhead · ${cohort.label}`}>
    <h3>Controller Overhead · {cohort.label}</h3>
    <p>Timing-only replay of the same workloads with frozen models. These measurements accompany all scheduling metrics in this cohort.</p>
    {cohort.entries.map(entry => <div key={entry.policy}>
      <p><strong>{entry.policy}</strong> · {entry.completed_runs}/{entry.selected_workloads} workloads completed{entry.failures.length > 0 ? ' · Partial timing coverage; failures retained' : ''}</p>
      <TimingMetrics timing={entry.pooled}/>
      <details><summary>{entry.policy} · overhead by workload</summary>
        <div className="table-scroll"><table><thead><tr><th>Workload</th><th>Status</th><th>Reviews</th><th>Total overhead · ms</th><th>P99 · µs</th><th>Completion · ticks</th><th>Overhead / completion</th><th>Overhead / Python replay</th></tr></thead><tbody>
          {entry.workloads.map(row => <tr key={row.workload_id}><td>{row.workload_id}</td><td>{row.status}</td><td>{number(row.timing.reviews, 0)}</td><td>{number(row.timing.controller_total_ms, 3)}</td><td>{number(row.timing.decision_p99_us, 3)}</td><td>{number(row.timing.makespan_ticks, 0)}</td><td>{percentage(row.timing.controller_vs_makespan_percent)}</td><td>{percentage(row.timing.controller_share_python_wall_percent)}</td></tr>)}
        </tbody></table></div>
      </details>
      {entry.failures.length > 0 && <p className="notice error">{entry.failures.map(f => `${f.workload_id}: ${f.reason}`).join('; ')}</p>}
    </div>)}
    <p className="subtle">Total overhead sums measured controller times, including rejected reviews. Percentages use ratios of totals across these workloads, rather than averages of workload percentages. Completion-time percentages are illustrative budgets; controller time is not charged to simulated schedules and is not measured process slowdown. Python replay percentage describes this simulator implementation.</p>
    <p className="subtle">Timing covers observed-feature extraction, prediction, safeguards and accepted queue updates; model loading, process dispatch, API requests and browser playback are excluded. Static policies have no ML controller; their dispatch overhead is unmeasured. Regression errors and accuracy are statistical summaries, so they have no separate process-completion overhead percentage.</p>
    <Source>dashboard/generated/controller_overhead.json · measured {snapshot.measured_at} · {snapshot.host.platform} · Python {snapshot.host.python}</Source>
  </div>;
}

export function DemoOverhead({result}) {
  return <div className="controller-overhead" aria-label="Selected simulation overhead">
    <h3>Controller Overhead · Selected Simulation</h3>
    {result.overhead ? <><TimingMetrics timing={result.overhead}/><p className="subtle">Measured during this full simulation, including rejected controller reviews. Ticks have no defined millisecond scale, so completion-time percentage is unavailable. Python replay percentage uses measured execution time. Model loading, dispatch, API and playback are excluded; cached results retain the original timing.</p></> : <p>ML controller overhead: not applicable to this static policy. Python dispatch overhead is unmeasured.</p>}
    <p>Charged context-switch overhead: <strong>{number(result.metrics.context_switch_time, 0)} ticks · {percentage(result.switch_overhead_percent)}</strong> of simulated completion time. This modeled charge is separate from measured controller overhead.</p>
  </div>;
}
