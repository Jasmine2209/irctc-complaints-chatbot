// src/config.js

// Backend API URL (your Render deployment)
export const BACKEND_URL = "https://irctc-complaints-chatbot-pn9k.onrender.com";

// Gemini API URL (from environment variable)
// Get your API key from: https://aistudio.google.com/app/apikey
export const GEMINI_API_URL = import.meta.env.VITE_GEMINI_API_URL || 
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=AIzaSyAZkuKOeZ-LvpHSpCqTA7pxTHOtTTWNJ-o";