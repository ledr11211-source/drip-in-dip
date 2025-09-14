from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

# تهيئة قاعدة البيانات
db = SQLAlchemy()

# إنشاء نموذج (Model) المستخدم
class User(db.Model, UserMixin): 
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    transactions = db.relationship('Transaction', backref='owner', lazy=True) 

# إنشاء نموذج (Model) المعاملات
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False) # إيراد أو مصروف أو سحب
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) 
    payment_method = db.Column(db.String(50), nullable=False) # عمود جديد لطريقة الدفع

    # دالة لمساعدتنا في رؤية البيانات بسهولة
    def __repr__(self):
        return f'<Transaction {self.description}>'