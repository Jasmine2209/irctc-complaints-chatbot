# 🚂 भोजन-मित्र (Bhojan Mitra) - IRCTC Complaint Chatbot

AI-powered chatbot for registering and routing IRCTC food and catering complaints.

## Features

- ✅ Automatic complaint classification (26 categories)
- ✅ Natural conversation (Google Gemini API)
- ✅ Complete database logging with analytics
- ✅ Mobile-responsive design
- ✅ QR code access ready

## Tech Stack

**Frontend:** React + Vite + Google Gemini API  
**Backend:** Python + Flask + SQLite + DistilBERT (Hugging Face)

## Installation

### Prerequisites
- Python 3.8+
- Node.js 18+
- Git

### Setup

1. **Clone repository:**
```bash
   git clone https://github.com/YOUR_USERNAME/irctc-complaints-chatbot.git
   cd irctc-complaints-chatbot
```

2. **Backend setup:**
```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Mac/Linux
   pip install -r requirements.txt
   python app.py
```
   
   Model will be automatically downloaded from Hugging Face on first run.

3. **Frontend setup:**
```bash
   cd frontend
   npm install
   npm run dev
```

4. **Environment variables:**
   
   Create `frontend/.env`:
```env
   VITE_API_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent
```

## Model

The trained DistilBERT model is hosted on Hugging Face:  
🤗 [YOUR_HF_USERNAME/YOUR_MODEL_NAME](https://huggingface.co/YOUR_HF_USERNAME/YOUR_MODEL_NAME)

## Database

Uses SQLite with 4 tables:
- `complaints` - Main complaint records
- `chat_messages` - Full conversation history
- `classification_logs` - Model performance tracking
- `analytics` - Daily statistics

## License

MIT License