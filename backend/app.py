import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import logging
from datetime import datetime, date


app = Flask(__name__)
CORS(app)

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///irctc_complaints.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GLOBAL VARIABLES - Model loads lazily
model = None
tokenizer = None
model_loading = False

COMPLAINT_CATEGORIES = {
    0: "Allergy violation", 1: "App failure", 2: "Cockroach",
    3: "Declining quality", 4: "Dietary violation", 5: "Dirty tray",
    6: "Double payment", 7: "Expired item", 8: "Fraud cancellation",
    9: "Hair in food", 10: "Missing items", 11: "No baby food",
    12: "No bill", 13: "No food option removed", 14: "No hot water",
    15: "No hygiene", 16: "No kids meal", 17: "Non-delivery",
    18: "Overcharging", 19: "Pantry closed early", 20: "Partial delivery",
    21: "Plastic waste", 22: "Refund delay", 23: "Rude staff",
    24: "Stale food", 25: "Stale roti"
}

CATEGORY_DEPARTMENTS = {
    "Allergy violation": "Food Safety & Medical",
    "App failure": "IT & Technical Support",
    "Cockroach": "Food Safety & Hygiene",
    "Declining quality": "Quality Assurance",
    "Dietary violation": "Food Safety & Compliance",
    "Dirty tray": "Hygiene & Sanitation",
    "Double payment": "Payment & Accounts",
    "Expired item": "Food Safety & Legal",
    "Fraud cancellation": "Fraud & Security",
    "Hair in food": "Food Safety & Hygiene",
    "Missing items": "Order Fulfillment",
    "No baby food": "Passenger Services",
    "No bill": "Compliance & Tax",
    "No food option removed": "Menu Planning",
    "No hot water": "Coach Maintenance",
    "No hygiene": "Food Safety & Hygiene",
    "No kids meal": "Food Services",
    "Non-delivery": "Delivery Operations",
    "Overcharging": "Billing & Finance",
    "Pantry closed early": "Pantry Operations",
    "Partial delivery": "Delivery Operations",
    "Plastic waste": "Environment & Sustainability",
    "Refund delay": "Refund & Accounts",
    "Rude staff": "HR & Staff Management",
    "Stale food": "Food Quality Control",
    "Stale roti": "Food Quality Control"
}

PRIORITY_MAP = {
    "Allergy violation": "Critical",
    "Cockroach": "Critical",
    "Expired item": "Critical",
    "Hair in food": "High",
    "No hygiene": "Critical",
    "Dietary violation": "High",
    "Fraud cancellation": "High",
    "Non-delivery": "High",
    "Stale food": "High",
    "Stale roti": "Medium",
}

# Database Models
class Complaint(db.Model):
    __tablename__ = 'complaints'
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    user_name = db.Column(db.String(100), nullable=False)
    user_email = db.Column(db.String(120), nullable=False, index=True)
    user_contact = db.Column(db.String(15), nullable=False)
    user_pnr = db.Column(db.String(10), nullable=False, index=True)
    train_number = db.Column(db.String(10), nullable=False, index=True)
    train_name = db.Column(db.String(100), nullable=False)
    coach = db.Column(db.String(10), nullable=False)
    seat = db.Column(db.String(10), nullable=False)
    complaint_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    category_id = db.Column(db.Integer, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    department = db.Column(db.String(100), nullable=False, index=True)
    status = db.Column(db.String(20), default='Registered', index=True)
    priority = db.Column(db.String(20), default='Medium')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    session_id = db.Column(db.String(100), nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(200), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'complaint_id': self.complaint_id,
            'user_name': self.user_name,
            'user_email': self.user_email,
            'user_contact': self.user_contact,
            'user_pnr': self.user_pnr,
            'train_number': self.train_number,
            'train_name': self.train_name,
            'coach': self.coach,
            'seat': self.seat,
            'complaint_text': self.complaint_text,
            'category': self.category,
            'confidence_score': self.confidence_score,
            'department': self.department,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
        }

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    was_classified = db.Column(db.Boolean, default=False)
    classified_category = db.Column(db.String(50), nullable=True)
    classification_confidence = db.Column(db.Float, nullable=True)

class ClassificationLog(db.Model):
    __tablename__ = 'classification_logs'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(100), nullable=False, index=True)
    input_text = db.Column(db.Text, nullable=False)
    predicted_category = db.Column(db.String(50), nullable=False)
    predicted_category_id = db.Column(db.Integer, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    top_predictions = db.Column(db.JSON, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    model_version = db.Column(db.String(50), default='v1.0')

class Analytics(db.Model):
    __tablename__ = 'analytics'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    total_complaints = db.Column(db.Integer, default=0)
    category_counts = db.Column(db.JSON, default={})
    department_counts = db.Column(db.JSON, default={})
    registered_count = db.Column(db.Integer, default=0)
    resolved_count = db.Column(db.Integer, default=0)
    avg_confidence_score = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def get_model():
    """LAZY LOAD - Only loads on first /classify request"""
    global model, tokenizer, model_loading
    
    if model is not None and tokenizer is not None:
        return model, tokenizer
    
    if model_loading:
        raise Exception("Model is loading, please wait...")
    
    try:
        model_loading = True
        logger.info("🔄 Loading model (first classification)...")
        
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        
        model_path = "./model"
        if os.path.exists(model_path):
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForSequenceClassification.from_pretrained(model_path)
        else:
            HF_MODEL_NAME = "jas2204/irctc-complaint-classifier"
            tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_NAME)
            model = AutoModelForSequenceClassification.from_pretrained(HF_MODEL_NAME)
        
        model.eval()
        logger.info(f"✅ Model loaded! Categories: {len(COMPLAINT_CATEGORIES)}")
        model_loading = False
        return model, tokenizer
        
    except Exception as e:
        model_loading = False
        logger.error(f"❌ Model load error: {e}")
        raise


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'IRCTC Complaint System API',
        'status': 'running',
        'endpoints': {
            'classify': '/classify',
            'register': '/complaint/register',
            'complaints': '/complaints',
            'health': '/health'
        }
    })


@app.route('/healthz', methods=['GET'])
@app.route('/health', methods=['GET'])
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'connected'
    except:
        db_status = 'disconnected'
    
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'database': db_status
    })


@app.route('/classify', methods=['POST'])
def classify():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data'}), 400
            
        text = data.get('text', '').strip()
        session_id = data.get('session_id', 'unknown')
        
        if not text:
            return jsonify({'error': 'Empty text'}), 400
        
        # Try to load model
        try:
            import torch
            current_model, current_tokenizer = get_model()
        except Exception as e:
            logger.error(f"Model load failed: {e}")
            return jsonify({
                'error': 'Model unavailable',
                'message': 'Upgrade to paid tier for ML classification',
                'fallback': True
            }), 503
        
        # Classify
        inputs = current_tokenizer(text, padding=True, truncation=True, max_length=128, return_tensors="pt")
        
        with torch.no_grad():
            outputs = current_model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            top3_values, top3_indices = torch.topk(predictions[0], 3)
            predicted_class = top3_indices[0].item()
            confidence = top3_values[0].item()
        
        category = COMPLAINT_CATEGORIES.get(predicted_class, "App failure")
        department = CATEGORY_DEPARTMENTS.get(category, "Customer Service")
        
        top_predictions = [
            {"category": COMPLAINT_CATEGORIES.get(top3_indices[i].item(), "Unknown"),
             "confidence": round(float(top3_values[i].item()), 4)}
            for i in range(3)
        ]
        
        # Log
        log = ClassificationLog(
            session_id=session_id,
            input_text=text,
            predicted_category=category,
            predicted_category_id=predicted_class,
            confidence_score=confidence,
            department=department,
            top_predictions=top_predictions
        )
        db.session.add(log)
        db.session.commit()
        
        logger.info(f"✅ Classified: {category} ({confidence:.1%})")
        
        return jsonify({
            'category': category,
            'category_id': predicted_class,
            'confidence': confidence,
            'department': department,
            'top_predictions': top_predictions
        })
    
    except Exception as e:
        logger.error(f"Classification error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/complaint/register', methods=['POST'])
def register_complaint():
    try:
        data = request.get_json()
        
        complaint = Complaint(
            complaint_id=data['complaint_id'],
            user_name=data['user_name'],
            user_email=data['user_email'],
            user_contact=data['user_contact'],
            user_pnr=data['user_pnr'],
            train_number=data['train_number'],
            train_name=data.get('train_name', ''),
            coach=data.get('coach', ''),
            seat=data.get('seat', ''),
            complaint_text=data['complaint_text'],
            category=data['category'],
            category_id=data['category_id'],
            confidence_score=data['confidence_score'],
            department=data['department'],
            priority=PRIORITY_MAP.get(data['category'], 'Medium'),
            session_id=data.get('session_id'),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:200]
        )
        
        db.session.add(complaint)
        db.session.commit()
        
        logger.info(f"✅ Registered: {complaint.complaint_id}")
        
        return jsonify({
            'success': True,
            'complaint_id': complaint.complaint_id,
            'message': 'Complaint registered'
        })
    
    except Exception as e:
        logger.error(f"Registration error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/complaints', methods=['GET'])
def get_complaints():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        complaints = Complaint.query.order_by(Complaint.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'complaints': [c.to_dict() for c in complaints.items],
            'total': complaints.total,
            'pages': complaints.pages
        })
    
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        return jsonify({'error': str(e)}), 500


# Initialize DB
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Database ready")
    except Exception as e:
        logger.error(f"DB init error: {e}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"🚀 Starting on port {port}")
    logger.info("⚡ Model: Lazy loading")
    
    # Use gunicorn in production
    app.run(host='0.0.0.0', port=port, debug=False)