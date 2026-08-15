import { Cpu, HardDrive, Gauge, Lightbulb } from 'lucide-react';

/**
 * The machine, rendered. Bench is the only screen that shows it.
 *
 * There used to be a `Diagnostics` modal above this, a framer-motion dialog on
 * `systemApi.diagnose()`. Nothing imported it -- it had been unreachable for
 * long enough that a redesign of it would have been invisible and skipping it
 * equally so -- and it was the last thing in the app holding framer-motion
 * open. Deleted rather than restyled. `systemApi.diagnose` is still exported
 * from utils/api.js with no caller; that was already true and is left alone.
 */
export function MachineReport({ report }) {
  const m = report?.machine;
  const e = report?.engine;
  const l = report?.limits;
  if (!m || !l) return null;

  // A GPU that exists but cannot be used is the single most confusing state,
  // so it is named rather than left for the user to infer from two numbers.
  const gpuLine = m.gpu_name
    ? `${m.gpu_name}${e?.gpu_offload_supported ? '' : ' (not usable by this build)'}`
    : 'none detected';

  /* A colophon: the page at the back of a book that names the press, the type
     and the stock. Four facts about the machine that will do the reading, set
     as a specification list -- label left, value right, leader dots between --
     rather than the icon-and-inline-style rows this was, which laid out four
     lines of a table by hand with a 7.5rem magic number holding the column. */
  return (
    <>
      <dl className="spec">
        <Row icon={<HardDrive size={14} />} label="Memory"
             value={`${m.available_ram_gb} GB free of ${m.total_ram_gb} GB`} />
        <Row icon={<Cpu size={14} />} label="Processor"
             value={`${m.cpu_cores} cores`} />
        <Row icon={<Gauge size={14} />} label="Graphics" value={gpuLine} />
        <Row icon={<Gauge size={14} />} label="Reads at once"
             value={`about ${Math.round(l.input_chars / 1000)}k characters`} />
      </dl>

      {report.advice?.length > 0 && (
        <div className="spec-advice">
          <h3><Lightbulb size={15} /> What this means</h3>
          <ul className="key-points">
            {report.advice.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </div>
      )}
    </>
  );
}

/* <dt>/<dd> and not two spans: this is a term and its definition, which is
   what a screen reader needs to hear to pair them. */
function Row({ icon, label, value }) {
  return (
    <div className="spec-row">
      <dt><span className="spec-icon">{icon}</span>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
