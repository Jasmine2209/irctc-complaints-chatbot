import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import logging
from datetime import datetime, date


app = Flask(__name__)
CORS(app)

# Database configuration - Use PostgreSQL for production
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///irctc_complaints.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# LAZY LOADING - Don't load model at startup
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
    """Main complaints table"""
    __tablename__ = 'complaints'
    
    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # User Information
    user_name = db.Column(db.String(100), nullable=False)
    user_email = db.Column(db.String(120), nullable=False, index=True)
    user_contact = db.Column(db.String(15), nullable=False)
    user_pnr = db.Column(db.String(10), nullable=False, index=True)
    train_number = db.Column(db.String(10), nullable=False, index=True)
    train_name = db.Column(db.String(100), nullable=False)
    coach = db.Column(db.String(10), nullable=False)
    seat = db.Column(db.String(10), nullable=False)
    
    # Complaint Details
    complaint_text = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, index=True)
    category_id = db.Column(db.Integer, nullable=False)
    confidence_score = db.Column(db.Float, nullable=False)
    department = db.Column(db.String(100), nullable=False, index=True)
    
    # Status Tracking
    status = db.Column(db.String(20), default='Registered', index=True)
    priority = db.Column(db.String(20), default='Medium')
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Additional metadata
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
    """Store all chat messages"""
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
    """Log all classification attempts"""
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
    """Store daily analytics"""
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
    """LAZY LOAD MODEL - Only load when first classification is requested"""
    global model, tokenizer, model_loading
    
    if model is not None and tokenizer is not None:
        return model, tokenizer
    
    if model_loading:
        raise Exception("Model is currently loading, please wait...")
    
    try:
        model_loading = True
        logger.info("🔄 Loading model (first request)...")
        
        model_path = "./model"
        
        # Try loading from local first
        if os.path.exists(model_path):
            logger.info(f"Loading from local path: {model_path}")
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForSequenceClassification.from_pretrained(model_path)
        else:
            # Load from Hugging Face
            HF_MODEL_NAME = "jas2204/irctc-complaint-classifier"
            logger.info(f"Loading from Hugging Face: {HF_MODEL_NAME}")
            tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_NAME)
            model = AutoModelForSequenceClassification.from_pretrained(HF_MODEL_NAME)
        
        model.eval()
        logger.info(f"✅ Model loaded successfully! Categories: {len(COMPLAINT_CATEGORIES)}")
        model_loading = False
        return model, tokenizer
        
    except Exception as e:
        model_loading = False
        logger.error(f"❌ Error loading model: {e}")
        raise


def update_daily_analytics():
    """Update daily analytics"""
    try:
        today = date.today()
        analytics = Analytics.query.filter_by(date=today).first()
        
        if not analytics:
            analytics = Analytics(date=today)
            db.session.add(analytics)
        
        today_start = datetime.combine(today, datetime.min.time())
        complaints = Complaint.query.filter(Complaint.created_at >= today_start).all()
        
        analytics.total_complaints = len(complaints)
        
        category_counts = {}
        department_counts = {}
        for complaint in complaints:
            category_counts[complaint.category] = category_counts.get(complaint.category, 0) + 1
            department_counts[complaint.department] = department_counts.get(complaint.department, 0) + 1
        
        analytics.category_counts = category_counts
        analytics.department_counts = department_counts
        
        analytics.registered_count = Complaint.query.filter(
            Complaint.created_at >= today_start,
            Complaint.status == 'Registered'
        ).count()
        
        analytics.resolved_count = Complaint.query.filter(
            Complaint.created_at >= today_start,
            Complaint.status == 'Resolved'
        ).count()
        
        if complaints:
            analytics.avg_confidence_score = sum(c.confidence_score for c in complaints) / len(complaints)
        
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Analytics update error: {e}")
        db.session.rollback()


@app.route('/', methods=['GET'])
def home():
    """Home endpoint"""
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
    """Health check with database status"""
    try:
        db.session.execute(db.text('SELECT 1'))
        db_status = 'connected'
    except:
        db_status = 'disconnected'
    
    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'database_status': db_status,
        'total_complaints': Complaint.query.count(),
        'total_classifications': ClassificationLog.query.count()
    })


@app.route('/classify', methods=['POST'])
def classify():
    """Classify complaint and log to database - Model loads on first use"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        session_id = data.get('session_id', 'unknown')
        
        if not text:
            return jsonify({'error': 'Empty text'}), 400
        
        # LAZY LOAD MODEL HERE
        try:
            current_model, current_tokenizer = get_model()
        except Exception as e:
            return jsonify({
                'error': 'Model loading failed',
                'message': str(e)
            }), 500
        
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
        
        # Log to database
        classification_log = ClassificationLog(
            session_id=session_id,
            input_text=text,
            predicted_category=category,
            predicted_category_id=predicted_class,
            confidence_score=confidence,
            department=department,
            top_predictions=top_predictions,
            model_version='v1.0'
        )
        db.session.add(classification_log)
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
        logger.error(f"❌ Classification error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/complaint/register', methods=['POST'])
def register_complaint():
    """Register complete complaint to database"""
    try:
        data = request.json
        
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
            status='Registered',
            session_id=data.get('session_id'),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:200]
        )
        
        db.session.add(complaint)
        db.session.commit()
        
        update_daily_analytics()
        
        logger.info(f"✅ Complaint registered: {complaint.complaint_id}")
        
        return jsonify({
            'success': True,
            'complaint_id': complaint.complaint_id,
            'message': 'Complaint registered successfully'
        })
    
    except Exception as e:
        logger.error(f"❌ Complaint registration error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/message/log', methods=['POST'])
def log_message():
    """Log chat message"""
    try:
        data = request.json
        
        message = ChatMessage(
            session_id=data['session_id'],
            role=data['role'],
            message=data['message'],
            was_classified=data.get('was_classified', False),
            classified_category=data.get('classified_category'),
            classification_confidence=data.get('classification_confidence')
        )
        
        db.session.add(message)
        db.session.commit()
        
        return jsonify({'success': True})
    
    except Exception as e:
        logger.error(f"❌ Message logging error: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/complaints', methods=['GET'])
def get_complaints():
    """Get complaints with filtering"""
    try:
        status = request.args.get('status')
        category = request.args.get('category')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        query = Complaint.query
        
        if status:
            query = query.filter_by(status=status)
        if category:
            query = query.filter_by(category=category)
        
        complaints = query.order_by(Complaint.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'complaints': [c.to_dict() for c in complaints.items],
            'total': complaints.total,
            'pages': complaints.pages,
            'current_page': page
        })
    
    except Exception as e:
        logger.error(f"❌ Complaints fetch error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/analytics/daily', methods=['GET'])
def get_daily_analytics():
    """Get daily analytics"""
    try:
        days = request.args.get('days', 7, type=int)
        
        analytics = Analytics.query.order_by(Analytics.date.desc()).limit(days).all()
        
        return jsonify({
            'analytics': [{
                'date': a.date.isoformat(),
                'total_complaints': a.total_complaints,
                'category_counts': a.category_counts,
                'department_counts': a.department_counts,
                'avg_confidence': a.avg_confidence_score
            } for a in analytics]
        })
    
    except Exception as e:
        logger.error(f"❌ Analytics fetch error: {e}")
        return jsonify({'error': str(e)}), 500


# Initialize database tables
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚂 IRCTC Complaint System")
    logger.info("=" * 60)
    logger.info("⚡ Model: Lazy Loading (loads on first /classify request)")
    logger.info("📊 Database: Connected")
    logger.info("=" * 60)
    
    # Get port from environment variable (Render provides this)
    port = int(os.environ.get('PORT', 5000))
    
    logger.info(f"🚀 Server starting on port {port}")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)