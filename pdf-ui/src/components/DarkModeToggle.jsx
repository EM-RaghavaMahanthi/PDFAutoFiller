import React from "react";
import { useEffect, useState } from 'react';

export default function DarkModeToggle() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", enabled);
  }, [enabled]);

  return (
    <button onClick={() => setEnabled(!enabled)} className="text-sm text-gray-500 dark:text-gray-300">
      {enabled ? "☀ Light Mode" : "🌙 Dark Mode"}
    </button>
  );
}