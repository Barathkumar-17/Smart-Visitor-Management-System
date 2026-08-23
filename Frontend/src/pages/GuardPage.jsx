import { useState } from 'react';
import GateEntry from './guard/GateEntry';
import Checkpoint from './guard/Checkpoint';
import GateExit from './guard/GateExit';

const TABS = [
  { key: 'entry', label: 'Gate in', Screen: GateEntry },
  { key: 'zone', label: 'Checkpoint', Screen: Checkpoint },
  { key: 'exit', label: 'Gate out', Screen: GateExit },
];

export default function GuardPage() {
  const [tab, setTab] = useState('entry');
  const { Screen } = TABS.find((t) => t.key === tab) ?? TABS[0];

  return (
    <div className="guard-screen">
      <div className="tab-row" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={t.key === tab}
            className={`tab${t.key === tab ? ' selected' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <Screen key={tab} />
    </div>
  );
}
