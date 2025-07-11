import React from "react";

export default function StatusLog({ logs }) {
  return (
    <div className="bg-gray-800 text-white rounded p-4 h-64 overflow-y-auto mb-4">
      {logs.length === 0 ? (
        <p className="text-gray-400">No logs yet.</p>
      ) : (
        logs.map((log, idx) => (
          <div key={idx} className="mb-1">
            {log}
          </div>
        ))
      )}
    </div>
  );
}
