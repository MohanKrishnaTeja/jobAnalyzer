import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import './StreamingChatInterface.css'; // We'll create this for basic styling

const StreamingChatInterface = ({ backendUrl = 'http://localhost:8000/api/jobs/complete-analysis/' }) => {
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState([]);
  const [eventSourceInstance, setEventSourceInstance] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages]);

  useEffect(() => {
    // Cleanup function to close EventSource connection
    return () => {
      if (eventSourceInstance) {
        eventSourceInstance.close();
      }
    };
  }, [eventSourceInstance]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    const userMessage = {
      id: Date.now(),
      sender: 'user',
      type: 'text',
      content: inputValue,
    };
    setMessages((prevMessages) => [...prevMessages, userMessage]);
    
    const currentInput = inputValue;
    setInputValue('');

    // Close any existing connection
    if (eventSourceInstance) {
      eventSourceInstance.close();
    }

    try {
      // Step 1: POST request to initiate the process
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ curriculum_text: currentInput }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Step 2: Establish SSE connection
      const es = new EventSource(`${backendUrl}?curriculum_text=${encodeURIComponent(currentInput)}`);
      setEventSourceInstance(es);

      es.onopen = () => {
        console.log('SSE connection opened.');
      };

      es.onmessage = (event) => {
        try {
          const parsedData = JSON.parse(event.data);
          console.log('Received SSE data:', parsedData); // Debug log
          
          const botMessage = {
            id: Date.now(),
            sender: 'bot',
            type: 'text',
            content: '',
          };

          // Handle different types of content based on the step
          if (parsedData.step === 'skills_extracted' || 
              parsedData.step === 'roles_identified' || 
              parsedData.step === 'gaps_analyzed') {
            botMessage.type = 'list';
            botMessage.content = Array.isArray(parsedData.data) ? parsedData.data : 
                               (parsedData.data.missing_skills || parsedData.data.job_market_skills || []);
          } else if (parsedData.step === 'summary_generated' || 
                    parsedData.step === 'major_project_generated' || 
                    parsedData.step === 'mini_projects_generated') {
            botMessage.type = 'markdown';
            botMessage.content = parsedData.data;
          } else if (parsedData.message) {
            botMessage.type = 'text';
            botMessage.content = parsedData.message;
          }

          // Add step information to the message for better context
          if (parsedData.step) {
            botMessage.step = parsedData.step;
          }
          
          setMessages((prevMessages) => [...prevMessages, botMessage]);

          if (parsedData.step === 'complete') {
            es.close();
            setEventSourceInstance(null);
            console.log('SSE stream complete, connection closed.');
          }
        } catch (error) {
          console.error('Failed to parse SSE message data:', event.data, error);
          const errorMessage = {
            id: Date.now(),
            sender: 'bot',
            type: 'error',
            content: `Error processing message: ${error.message}`,
          };
          setMessages((prevMessages) => [...prevMessages, errorMessage]);
        }
      };

      es.onerror = (error) => {
        console.error('EventSource failed:', error);
        const errorMessage = {
          id: Date.now(),
          sender: 'bot',
          type: 'error',
          content: 'Connection error or stream ended.',
        };
        setMessages((prevMessages) => [...prevMessages, errorMessage]);
        es.close();
        setEventSourceInstance(null);
      };

    } catch (error) {
      console.error('Error in request:', error);
      const errorMessage = {
        id: Date.now(),
        sender: 'bot',
        type: 'error',
        content: `Error: ${error.message}`,
      };
      setMessages((prevMessages) => [...prevMessages, errorMessage]);
    }
  };

  return (
    <div className="streaming-chat-interface">
      <div className="messages-area">
        {messages.map((msg) => (
          <div key={msg.id} className={`message ${msg.sender}`}>
            {msg.type === 'text' && <p>{msg.content}</p>}
            {msg.type === 'markdown' && (
              <div className="markdown-content">
                <ReactMarkdown>{String(msg.content)}</ReactMarkdown>
              </div>
            )}
            {msg.type === 'list' && (
              <div className="list-content">
                <h4>{msg.step === 'skills_extracted' ? 'Extracted Skills:' : 
                     msg.step === 'roles_identified' ? 'Identified Roles:' : 
                     msg.step === 'gaps_analyzed' ? 'Missing Skills:' : 'List:'}</h4>
                <ul>
                  {msg.content.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>
            )}
            {msg.type === 'error' && <p className="error-message">{msg.content}</p>}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
      <form onSubmit={handleSubmit} className="input-area">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Type your message..."
        />
        <button type="submit">Submit</button>
      </form>
    </div>
  );
};

export default StreamingChatInterface;
