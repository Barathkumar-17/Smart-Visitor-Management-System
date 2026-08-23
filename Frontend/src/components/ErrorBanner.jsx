export default function ErrorBanner({ error, onDismiss }) {
  if (!error) return null;
  const code = error.code ?? 'Error';
  const message = error.message ?? String(error);
  return (
    <div className="error-banner" role="alert">
      <div>
        <strong>{code}</strong>
        <span>{message}</span>
      </div>
      {onDismiss && (
        <button type="button" className="link-button" onClick={onDismiss}>
          dismiss
        </button>
      )}
    </div>
  );
}
