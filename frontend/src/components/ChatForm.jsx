import React, { useRef } from "react";

const ChatForm = ({ chatHistory, setChatHistory, generateBotResponse }) => {
  const inputRef = useRef();

  const handleFormSubmit = (e) => {
    e.preventDefault();
    const userMessage = inputRef.current.value.trim();
    if (!userMessage) return;
    inputRef.current.value = "";

    const updatedHistory = [
      ...chatHistory, {role: "user", text: userMessage},
      {role: "model", text: "Thinking..."}
    ];

    setChatHistory(updatedHistory);

    generateBotResponse([
      ...chatHistory, {role: "user", text: `Using the details provided above, please address this query: ${userMessage}`}
    ]);
  };

  return (
    <form action="chat-form" className="chat-form" onSubmit={handleFormSubmit}>
      <input
        ref={inputRef}
        type="text"
        placeholder="Message..."
        className="message-input"
        required
      />
      <button className="material-symbols-outlined">arrow_upward_alt</button>
    </form>
  );
};

export default ChatForm;





