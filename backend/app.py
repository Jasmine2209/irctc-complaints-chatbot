import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import logging
from datetime import datetime, date
import re


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

# KEYWORD-BASED CLASSIFICATION RULES
CLASSIFICATION_RULES = {
    "Allergy violation": ["allergy", "allergic", "reaction", "allergen", "nut", "peanut", "shellfish", "lactose"],
    "App failure": ["app crash", "not working", "app error", "technical issue", "app problem", "bug", "glitch", "app down"],
    "Cockroach": ["cockroach", "roach", "insect", "bug in food", "pest"],
    "Declining quality": ["quality declined", "worse than before", "not good anymore", "quality dropped"],
    "Dietary violation": ["non-veg in veg", "meat in vegetarian", "jain food", "religious", "halal", "kosher"],
    "Dirty tray": ["dirty tray", "unclean tray", "filthy tray", "tray not clean"],
    "Double payment": ["charged twice", "double charge", "paid twice", "duplicate payment", "double debit"],
    "Expired item": ["expired", "expiry date", "past expiry", "old product", "outdated"],
    "Fraud cancellation": ["fraud", "scam", "cancelled without reason", "fake cancellation", "cheating"],
    "Hair in food": ["hair in", "found hair", "strand of hair", "human hair"],
    "Missing items": ["didn't receive", "missing", "not delivered all", "incomplete order", "items missing"],
    "No baby food": ["baby food", "infant food", "no food for baby", "child food unavailable"],
    "No bill": ["no bill", "bill not provided", "receipt missing", "invoice not given", "no receipt"],
    "No food option removed": ["removed from menu", "not available", "discontinued", "option not there"],
    "No hot water": ["cold water", "no hot water", "lukewarm", "not heated"],
    "No hygiene": ["unhygienic", "no hygiene", "unsanitary", "dirty", "filthy", "not clean"],
    "No kids meal": ["kids meal", "children food", "no food for kids", "child portion"],
    "Non-delivery": ["not delivered", "didn't deliver", "no delivery", "never received", "order not came"],
    "Overcharging": ["overcharged", "too expensive", "charged extra", "high price", "excess charge"],
    "Pantry closed early": ["pantry closed", "closed early", "shut before time", "not available"],
    "Partial delivery": ["partial", "incomplete", "only some items", "missing some"],
    "Plastic waste": ["plastic", "environmental", "too much packaging", "waste", "non-biodegradable"],
    "Refund delay": ["refund not received", "refund delayed", "money not back", "waiting for refund"],
    "Rude staff": ["rude", "misbehave", "impolite", "unprofessional", "bad behavior", "staff attitude"],
    "Stale food": ["stale", "not fresh", "old food", "spoiled", "bad smell", "rotten", "smells bad"],
    "Stale roti": ["stale roti", "hard roti", "old roti", "roti not fresh"]
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
    model_version = db.Column(db.String(50), default='rule-based-v1.0')

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


def classify_complaint_rule_based(text):
    """Rule-based classification using keywords"""
    text_lower = text.lower()
    
    # Score each category based on keyword matches
    scores = {}
    for category, keywords in CLASSIFICATION_RULES.items():
        score = 0
        matched_keywords = []
        
        for keyword in keywords:
            if keyword in text_lower:
                score += 1
                matched_keywords.append(keyword)
        
        if score > 0:
            scores[category] = {
                'score': score,
                'keywords': matched_keywords
            }
    
    # If no matches, default to "App failure"
    if not scores:
        category = "App failure"
        category_id = 1
        confidence = 0.50
    else:
        # Get top 3 matches
        sorted_categories = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)
        
        # Best match
        category = sorted_categories[0][0]
        category_id = list(COMPLAINT_CATEGORIES.values()).index(category)
        
        # Calculate confidence (simple heuristic)
        total_score = sum(s['score'] for _, s in sorted_categories)
        confidence = min(0.95, 0.70 + (scores[category]['score'] / total_score) * 0.25)
    
    department = CATEGORY_DEPARTMENTS.get(category, "Customer Service")
    
    # Generate top 3 predictions
    top_predictions = []
    if scores:
        sorted_cats = sorted(scores.items(), key=lambda x: x[1]['score'], reverse=True)[:3]
        total = sum(s['score'] for _, s in sorted_cats)
        
        for cat, data in sorted_cats:
            cat_id = list(COMPLAINT_CATEGORIES.values()).index(cat)
            conf = 0.70 + (data['score'] / total) * 0.25
            top_predictions.append({
                'category': cat,
                'confidence': round(min(0.95, conf), 4)
            })
    else:
        top_predictions = [
            {'category': 'App failure', 'confidence': 0.50},
            {'category': 'Declining quality', 'confidence': 0.30},
            {'category': 'Rude staff', 'confidence': 0.20}
        ]
    
    return category, category_id, confidence, department, top_predictions


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'message': 'IRCTC Complaint System API',
        'status': 'running',
        'classification': 'rule-based (optimized for free tier)',
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
        'classification': 'rule-based',
        'database': db_status,
        'total_complaints': Complaint.query.count()
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
        
        # Rule-based classification (fast, no memory issues)
        category, category_id, confidence, department, top_predictions = classify_complaint_rule_based(text)
        
        # Log to database
        log = ClassificationLog(
            session_id=session_id,
            input_text=text,
            predicted_category=category,
            predicted_category_id=category_id,
            confidence_score=confidence,
            department=department,
            top_predictions=top_predictions,
            model_version='rule-based-v1.0'
        )
        db.session.add(log)
        db.session.commit()
        
        logger.info(f"✅ Classified: {category} ({confidence:.1%})")
        
        return jsonify({
            'category': category,
            'category_id': category_id,
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
            'message': 'Complaint registered successfully'
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
        status = request.args.get('status')
        
        query = Complaint.query
        if status:
            query = query.filter_by(status=status)
        
        complaints = query.order_by(Complaint.created_at.desc()).paginate(
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


@app.route('/message/log', methods=['POST'])
def log_message():
    try:
        data = request.get_json()
        
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
        logger.error(f"Message log error: {e}")
        db.session.rollback()
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
    logger.info("=" * 60)
    logger.info("🚂 IRCTC Complaint System - Rule-Based Classification")
    logger.info("=" * 60)
    logger.info("✅ Optimized for free tier (no ML model)")
    logger.info(f"🚀 Starting on port {port}")
    logger.info("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)