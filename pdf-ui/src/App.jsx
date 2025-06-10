import React from 'react';
import { useState } from 'react';
import UploadForm from './components/UploadForm';
import StatusLog from './components/StatusLog';
import DownloadButton from './components/DownloadButton';
import DarkModeToggle from './components/DarkModeToggle';

export default function App() {
  const [jobId, setJobId] = useState(null);
  const [statusLogs, setStatusLogs] = useState([]);
  const [done, setDone] = useState(false);

  const handleJobStart = (id) => {
    setJobId(id);
    setStatusLogs(["📄 Job Started..."]);
    setDone(false);

    const eventSource = new EventSource(`/stream/${id}`);
    eventSource.onmessage = (e) => {
      setStatusLogs((prev) => [...prev, `✅ ${e.data}`]);
      if (e.data.includes("Done filling.")) {
        setDone(true);
        eventSource.close();
      }
    };
  };

  return (
    <div className="min-h-screen bg-gray-100 dark:bg-gray-900 text-gray-900 dark:text-white transition-colors">
      <div className="max-w-2xl mx-auto py-12 px-6">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">PDF AutoFiller</h1>
          <DarkModeToggle />
        </div>
        <UploadForm onJobStart={handleJobStart} />
        <StatusLog logs={statusLogs} />
        {done && <DownloadButton jobId={jobId} />}
      </div>
    </div>
  );
}