import { useEffect, useState } from 'react';
import { getPhotoDataUrl } from '../api/photos';

function initialsOf(name) {
  return (name || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('');
}

export default function PhotoCard({ person }) {
  const ref = person?.photo_ref;
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let active = true;
    setSrc(null);
    getPhotoDataUrl(ref).then((url) => {
      if (active) setSrc(url);
    });
    return () => {
      active = false;
    };
  }, [ref]);

  return (
    <figure className="photo-card">
      <div className="photo-frame">
        {src ? (
          <img src={src} alt={person.name || 'Visitor'} />
        ) : (
          <span className="photo-initials">{initialsOf(person?.name)}</span>
        )}
      </div>
      <figcaption>
        <span className="photo-name">{person?.name || 'Unnamed'}</span>
        <span className={`photo-role role-${person?.role || 'unknown'}`}>{person?.role}</span>
      </figcaption>
    </figure>
  );
}
