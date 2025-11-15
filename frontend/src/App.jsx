import { useEffect, useState, useRef } from "react";
import ChatbotIcon from "./components/ChatbotIcon";
import ChatForm from "./components/ChatForm";
import ChatMessage from "./components/ChatMessage";
import { companyInfo } from "./components/companyInfo";

const App = () => {
  const [chatHistory, setChatHistory] = useState([{
    hideInChat: true,
    role: "model",
    text: companyInfo,
  }]);
  const [showChatbot, setShowChatbot] = useState(false);
  const [sessionId] = useState(() => 
    `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );
  const [complaintData, setComplaintData] = useState(null);
  
  const chatBodyRef = useRef();

  // Log message to database
  const logMessage = async (role, message, classificationData = null) => {
    try {
      await fetch("http://127.0.0.1:5000/message/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          role: role,
          message: message,
          was_classified: classificationData !== null,
          classified_category: classificationData?.category,
          classification_confidence: classificationData?.confidence
        })
      });
    } catch (error) {
      console.error("Message logging error:", error);
    }
  };

  // Classify complaint using backend
  const classifyComplaint = async (complaintText) => {
    try {
      const response = await fetch("http://127.0.0.1:5000/classify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          text: complaintText,
          session_id: sessionId 
        })
      });

      const data = await response.json();
      
      if (response.ok && data.category) {
        console.log(`✅ Classified as: ${data.category} (${(data.confidence * 100).toFixed(1)}%)`);
        return {
          category: data.category,
          category_id: data.category_id,
          confidence: data.confidence || 0,
          department: data.department || "Customer Service",
          top_predictions: data.top_predictions || []
        };
      }
      
      return null;
    } catch (error) {
      console.error("Classification error:", error);
      return null;
    }
  };

  // Register complete complaint to database
  const registerComplaint = async (complaintDetails) => {
    try {
      const response = await fetch("http://127.0.0.1:5000/complaint/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...complaintDetails,
          session_id: sessionId
        })
      });

      const data = await response.json();
      
      if (response.ok) {
        console.log(`✅ Complaint registered to database: ${data.complaint_id}`);
        return true;
      }
      
      console.error("Failed to register complaint:", data);
      return false;
    } catch (error) {
      console.error("Complaint registration error:", error);
      return false;
    }
  };

  // Extract complaint details from conversation
  const extractComplaintDetails = (conversation) => {
    // Try to find complaint ID (format: IRC followed by numbers)
    const complaintIdMatch = conversation.match(/#(IRC\d+)/);
    
    // Extract user details with flexible patterns
    const nameMatch = conversation.match(/(?:Name|name|NAME)[:;\s-]*([A-Za-z\s]+?)(?:[,\n]|Email|email|Contact|contact|PNR|pnr|Train|train)/);
    const emailMatch = conversation.match(/(?:Email|email|EMAIL)[:;\s-]*([\w\.-]+@[\w\.-]+\.\w+)/);
    const contactMatch = conversation.match(/(?:Contact|contact|CONTACT|Phone|phone|Mobile|mobile)[:;\s-]*(\d{10})/);
    const pnrMatch = conversation.match(/(?:PNR|pnr)[:;\s-]*(\d{10})/);
    const trainNumberMatch = conversation.match(/(?:Train [Nn]umber|train number|TRAIN NUMBER)[:;\s-]*(\d{5})/);
    const trainNameMatch = conversation.match(/(?:Train [Nn]ame|train name|TRAIN NAME)[:;\s-]*([A-Za-z0-9\s]+?)(?:[,\n]|Coach|coach|Seat|seat|$)/);
    const coachMatch = conversation.match(/(?:Coach|coach|COACH)[:;\s-]*([A-Z0-9]+)/);
    const seatMatch = conversation.match(/(?:Seat|seat|SEAT)[:;\s-]*(\d+)/);
    
    // Log extraction results for debugging
    console.log("Extraction results:", {
      complaintId: complaintIdMatch?.[1],
      name: nameMatch?.[1],
      email: emailMatch?.[1],
      contact: contactMatch?.[1],
      pnr: pnrMatch?.[1],
      trainNumber: trainNumberMatch?.[1],
      trainName: trainNameMatch?.[1]
    });
    
    // Minimum required fields (including train name and number)
    if (complaintIdMatch && nameMatch && emailMatch && contactMatch && pnrMatch && trainNumberMatch && trainNameMatch) {
      return {
        complaint_id: complaintIdMatch[1],
        user_name: nameMatch[1].trim(),
        user_email: emailMatch[1],
        user_contact: contactMatch[1],
        user_pnr: pnrMatch[1],
        train_number: trainNumberMatch[1],
        train_name: trainNameMatch[1].trim(),
        coach: coachMatch ? coachMatch[1] : null,
        seat: seatMatch ? seatMatch[1] : null
      };
    }
    
    return null;
  };

  const generateBotResponse = async (history) => {
    const updateHistory = (text, isError = false) => {
      setChatHistory(prev => [
        ...prev.filter(msg => msg.text !== "Thinking..."), 
        { role: "model", text, isError }
      ]);
    };

    const latestUserMessage = history[history.length - 1].text;

    // Log user message to database
    await logMessage("user", latestUserMessage);

    // Check if it's likely a complaint
    const complaintKeywords = [
      'stale', 'hair', 'cockroach', 'dirty', 'rude', 'refund', 'expired',
      'overcharge', 'missing', 'delay', 'allergy', 'cold', 'bad', 'terrible',
      'wrong', 'problem', 'issue', 'complaint', 'dal', 'roti', 'food', 'order',
      'watery', 'soggy', 'spoiled', 'late', 'burnt', 'raw', 'smelly', 'disgusting',
      'awful', 'horrible', 'unhygienic', 'not delivered', 'didnt receive', 'never got'
    ];

    const isLikelyComplaint = complaintKeywords.some(keyword => 
      latestUserMessage.toLowerCase().includes(keyword)
    );

    let classification = null;
    let enhancedPrompt = "";

    // If it's a complaint, classify it
    if (isLikelyComplaint) {
      console.log("🔍 Complaint detected, classifying...");
      classification = await classifyComplaint(latestUserMessage);
      
      if (classification) {
        console.log(`✅ Classification successful: ${classification.category}`);
        
        // Store classification data for later use
        setComplaintData(prev => ({
          ...prev,
          complaint_text: latestUserMessage,
          category: classification.category,
          category_id: classification.category_id,
          confidence_score: classification.confidence,
          department: classification.department
        }));

        // Add classification context for Gemini - NOW INCLUDES TRAIN NAME
        enhancedPrompt = `\n\n[SYSTEM CONTEXT: The user's complaint has been automatically classified as "${classification.category}" with ${(classification.confidence * 100).toFixed(1)}% confidence. This complaint will be routed to the ${classification.department} department. 

IMPORTANT: When the user provides their personal details, you MUST ask for ALL of the following in this order:
1. Name
2. Email
3. Contact Number (10 digits)
4. PNR (10 digits)
5. Train Number (5 digits)
6. Train Name (full name of the train, e.g., "Rajdhani Express", "Shatabdi Express")
7. Coach (optional)
8. Seat (optional)

Once ALL required information (Name, Email, Contact, PNR, Train Number, AND Train Name) is provided, generate a unique complaint ID in this format: IRC[YYYYMMDDHHMMSS][4-random-digits] (example: IRC202501101430521234). 

Then confirm the complaint registration and include the classification category naturally in your response.]`;
      }
    }

    // Format chat history for Gemini API
    const formattedHistory = history.map(({ role, text }) => ({ 
      role, 
      parts: [{ text: text + (role === "user" && classification ? enhancedPrompt : "") }] 
    }));

    const requestOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contents: formattedHistory })
    };

    try {
      // Call Gemini API
      const response = await fetch(import.meta.env.VITE_API_URL, requestOptions);
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error?.message || "Something went wrong. Try again later.");
      }

      // Get Gemini's response
      let apiResponseText = data.candidates[0].content.parts[0].text
        .replace(/\*\*(.*?)\*\*/g, "$1")
        .trim();

      // Log bot response to database
      await logMessage("model", apiResponseText, classification);

      // Check if complaint was confirmed (contains complaint ID)
      const complaintIdMatch = apiResponseText.match(/#(IRC\d+)/);
      
      if (complaintIdMatch && complaintData) {
        console.log(`🎯 Complaint ID detected: ${complaintIdMatch[1]}`);
        console.log("📋 Attempting to extract user details...");
        
        // Extract user details from the entire conversation
        const fullConversation = history.map(h => h.text).join("\n") + "\n" + apiResponseText;
        const extractedDetails = extractComplaintDetails(fullConversation);
        
        if (extractedDetails) {
          console.log("✅ Details extracted successfully:", extractedDetails);
          
          // Register complaint to database
          const registered = await registerComplaint({
            ...extractedDetails,
            ...complaintData
          });
          
          if (registered) {
            console.log("🎉 Complaint successfully saved to database!");
          } else {
            console.error("❌ Failed to save complaint to database");
          }
          
          // Clear complaint data
          setComplaintData(null);
        } else {
          console.warn("⚠️ Could not extract all required details (including train name) from conversation");
        }
      }

      updateHistory(apiResponseText);

    } catch (error) {
      console.error("❌ API Error:", error);
      updateHistory(`Sorry, I encountered an error: ${error.message}. Please try again or call 139 for assistance.`, true);
    }
  };

  useEffect(() => {
    // Auto-scroll when chat updates
    if (chatBodyRef.current) {
      setTimeout(() => {
        chatBodyRef.current.scrollTo({ 
          top: chatBodyRef.current.scrollHeight, 
          behavior: "smooth" 
        });
      }, 100);
    }
  }, [chatHistory]);

  return (
    <div className={`container ${showChatbot ? "show-chatbot" : ""}`}>
      <button 
        id="chatbot-toggler" 
        onClick={() => setShowChatbot(prev => !prev)}
        aria-label="Toggle chatbot"
      >
        <span className="material-symbols-outlined">mode_comment</span>
        <span className="material-symbols-outlined">close</span>
      </button>

      <div className="chatbot-popup">
        {/* Header */}
        <div className="chat-header">
          <div className="header-info">
            <ChatbotIcon />
            <h2 className="logo-text">भोजन-मित्र</h2>
          </div>
          <button 
            onClick={() => setShowChatbot(prev => !prev)}
            aria-label="Minimize chatbot"
          >
            <span className="material-symbols-outlined">keyboard_arrow_down</span>
          </button>
        </div>

        {/* Chat Body */}
        <div ref={chatBodyRef} className="chat-body">
          <div className="message bot-message">
            <ChatbotIcon />
            <p className="message-text">
              Hello! 👋<br />
              I'm Bhojan Mitra, your IRCTC complaint assistant. How can I help you today?
            </p>
          </div>

          {/* Render chat history */}
          {chatHistory.map((chat, index) => (
            <ChatMessage key={index} chat={chat} />
          ))}
        </div>

        {/* Chat Footer */}
        <div className="chat-footer">
          <ChatForm
            chatHistory={chatHistory}
            setChatHistory={setChatHistory}
            generateBotResponse={generateBotResponse}
          />
        </div>
      </div>
    </div>
  );
};

export default App;