import React, { useState, useEffect } from 'react';
import ChatInterface from './components/ChatInterface';
import './App.css';

function App() {
  const [apiStatus, setApiStatus] = useState({ fastapi: false, django: false });

  useEffect(() => {
    // Check API status
    const checkStatus = async () => {
      try {
        const fastapiResponse = await fetch('http://localhost:8001/health');
        const djangoResponse = await fetch('http://localhost:8000/health/');

        setApiStatus({
          fastapi: fastapiResponse.ok,
          django: djangoResponse.ok
        });
      } catch (error) {
        console.error('Error checking API status:', error);
      }
    };

    checkStatus();
    const interval = setInterval(checkStatus, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="App">
      <header className="App-header">
        <h1>🤖 LLM API Platform</h1>
        <p>
          Enterprise-grade Large Language Model API platform
        </p>
        <div className="status-indicators">
          <div className="status-item">
            <span className={`status-dot ${apiStatus.fastapi ? 'green' : 'red'}`}></span>
            <span>FastAPI: {apiStatus.fastapi ? 'Online' : 'Offline'}</span>
          </div>
          <div className="status-item">
            <span className={`status-dot ${apiStatus.django ? 'green' : 'red'}`}></span>
            <span>Django: {apiStatus.django ? 'Online' : 'Offline'}</span>
          </div>
        </div>
        <div className="quick-links">
          <a href="http://localhost:8001/docs" target="_blank" rel="noopener noreferrer">
            🚀 Enterprise FastAPI Docs
          </a>
          <a href="http://localhost:8000/admin/" target="_blank" rel="noopener noreferrer">
            ⚙️ Django Admin Panel
          </a>
          <a href="http://localhost:8080" target="_blank" rel="noopener noreferrer">
            🗄️ Database Admin
          </a>
          <a href="http://localhost:8025" target="_blank" rel="noopener noreferrer">
            📧 Email Testing
          </a>
        </div>
      </header>

      <main className="App-main">
        <ChatInterface />
      </main>
    </div>
  );
}

export default App;