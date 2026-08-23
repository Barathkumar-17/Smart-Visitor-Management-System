import { useState } from 'react';
import Inbox from './faculty/Inbox';
import ArrivalAck from './faculty/ArrivalAck';

const TABS = [
  { key: 'inbox', label: 'Inbox', Screen: Inbox },
  { key: 'ack', label: 'Arrival', Screen: ArrivalAck },
];

export default function FacultyPage() {
  const [tab, setTab] = useState('inbox');
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
