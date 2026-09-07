'use client';
import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
export function CopyButton({
  text,
  label = 'Copy code',
}: {
  text: string;
  label?: string;
}) {
  const [message, setMessage] = useState('');
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setMessage('Copied');
    } catch {
      setMessage('Copy unavailable');
    }
    setTimeout(() => setMessage(''), 2200);
  }
  return (
    <button
      className="copy-button"
      onClick={copy}
      aria-label={message || label}
    >
      {message === 'Copied' ? <Check size={16} /> : <Copy size={16} />}
      <span>{message}</span>
    </button>
  );
}
