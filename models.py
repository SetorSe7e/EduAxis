from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(225), nullable=False)
    role = db.Column(db.String(50), nullable=False) # director, teacher, guardian

class Guardian(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(20))
    phone = db.Column(db.String(20))
    relation = db.Column(db.String(50))
    students = db.relationship('Student', backref='guardian', lazy=True)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    birth_date = db.Column(db.Date)
    class_name = db.Column(db.String(50))
    guardian_id = db.Column(db.Integer, db.ForeignKey('guardian.id'), nullable=True)
    fees = db.relationship('Fee', backref='student', lazy=True)

class Fee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    month = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pendente')
    due_date = db.Column(db.Date)
    payment_date = db.Column(db.Date)