from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
import json
from sqlalchemy import text
from sqlalchemy.dialects.mysql import BINARY
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort
import re
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from hmac import compare_digest

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banking_management.db'
db = SQLAlchemy(app)
api = Api(app)
app.config['JWT_SECRET_KEY'] = 'super_secret_key'
jwt = JWTManager(app)

@app.route('/api/who-am-i', methods=['GET'])
@jwt_required()
def protected():
    identity = get_jwt()
    username = identity['username']
    role = identity['role']
    return jsonify({'message': f"Hello, {username}, your role is {role}"})

@jwt.user_identity_loader
def user_identity_lookup(user):
    return user

@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"] 
    user_id_uuid = uuid.UUID(hex=identity)
    user_id_binary = user_id_uuid.bytes 
    return User.query.filter_by(user_id=user_id_binary).one_or_none() 
    
from functools import wraps

def admin_required(fn):
    @wraps(fn)  # Preserve the original function name
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get('role') != 'ADMIN':
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper

def user_or_admin_required(fn):
    @wraps(fn)  # Preserve the original function name
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if 'role' not in claims or claims['role'] not in ['ADMIN', 'USER']:
            return jsonify({'error': 'Access denied'}), 403
        return fn(*args, **kwargs)
    return wrapper


@app.route('/api/admin-only', methods=['GET'])
@admin_required
def admin_only():
    return jsonify({'message': 'Welcome, Admin!'}), 200

def generate_uuid():
    return uuid.uuid4().bytes

class User(db.Model):
    __tablename__ = 'user'
    user_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.Enum('ADMIN', 'USER'), nullable=False, default='USER')
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id', onupdate='CASCADE', ondelete='RESTRICT'))

    customer = db.relationship('Customer', backref='user', uselist=False)

    def check_password(self, password):
        return compare_digest(password, self.password)

    def __repr__(self):
        return f"User(user_id={self.user_id}, username={self.username}, role={self.role})"

class Branch(db.Model):
    __tablename__ = 'branch'
    
    branch_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid, nullable=False)
    branch_name = db.Column(db.String(100), unique=True, nullable=False)
    address_line1 = db.Column(db.String(100), nullable=False)
    address_line2 = db.Column(db.String(100))
    city = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)

    # Relationships
    accounts = db.relationship('Account', backref='branch', lazy=True)
    employees = db.relationship('Employee', backref='branch', lazy=True)

    def __repr__(self):
        return (
            f"Branch("
            f"branch_id = {self.branch_id.hex()}, "  # Convert binary UUID to hex for readability
            f"branch_name = {self.branch_name}, "
            f"address_line1 = {self.address_line1}, "
            f"address_line2 = {self.address_line2}, "
            f"city = {self.city}, "
            f"zip_code = {self.zip_code}, "
            f"phone_number = {self.phone_number})"
        )
    
class Customer(db.Model):
    __tablename__ = 'customer'
    
    customer_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    wage_declaration = db.Column(db.DECIMAL(15, 2), default=0)

    # Relationships
    accounts = db.relationship('Account', backref='customer', cascade='all, delete-orphan')
    loans = db.relationship('Loan', backref='customer', cascade='all, delete-orphan')
    support_tickets = db.relationship('CustomerSupport', backref='customer', cascade='all, delete-orphan')
    credit_score = db.relationship('CreditScore', backref='customer', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f"Customer(customer_id = {self.customer_id}, first_name = {self.first_name}, last_name = {self.last_name}, date_of_birth = {self.date_of_birth}, phone_number = {self.phone_number}, email = {self.email}, address_line1 = {self.address_line1}, address_line2 = {self.address_line2}, city = {self.city}, zip_code = {self.zip_code}, wage_declaration = {self.wage_declaration})"

class Account(db.Model):
    __tablename__ = 'account'
    
    account_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    account_type = db.Column(db.Enum('CHECKING', 'SAVINGS'), nullable=False)
    balance = db.Column(db.DECIMAL(15,2), nullable=False, default=0.00)
    creation_date = db.Column(db.DateTime, nullable=False)
    branch_id = db.Column(BINARY(16), db.ForeignKey('branch.branch_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)

    cards = db.relationship('Card', backref='account', cascade='all, delete-orphan')
    outgoing_transactions = db.relationship('Transaction', foreign_keys='Transaction.from_account_id', backref='from_account', cascade='all, delete-orphan')
    incoming_transactions = db.relationship('Transaction', foreign_keys='Transaction.to_account_id', backref='to_account', cascade='all, delete-orphan')

    __table_args__ = (
        db.CheckConstraint('balance >= 0', name='check_balance_positive'),
    )
    
    def __repr__(self):
        return f"Account(account_id = {self.account_id}, customer_id = {self.customer_id}, account_type = {self.account_type}, balance = {self.balance}, creation_date = {self.creation_date}, branch_id = {self.branch_id})"

class Loan(db.Model):
    __tablename__ = 'loan'
    
    loan_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    loan_type = db.Column(db.Enum('HOME', 'AUTO', 'PERSONAL'), nullable=False)
    principal_amount = db.Column(db.DECIMAL(15,2), nullable=False)
    interest_rate = db.Column(db.DECIMAL(5,2), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum('ACTIVE', 'PAID_OFF', 'DEFAULT'), nullable=False)

    payments = db.relationship('LoanPayment', backref='loan', cascade='all, delete-orphan')

    __table_args__ = (
        db.CheckConstraint('principal_amount > 0', name='check_principal_positive'),
        db.CheckConstraint('interest_rate >= 0', name='check_interest_non_negative'),
        db.CheckConstraint('start_date < end_date', name='check_dates_valid'),
    )
    
    def __repr__(self):
        return f"Loan(loan_id = {self.loan_id}, customer_id = {self.customer_id}, loan_type = {self.loan_type}, principal_amount = {self.principal_amount}, interest_rate = {self.interest_rate}, start_date = {self.start_date}, end_date = {self.end_date}, status = {self.status})"

class LoanPayment(db.Model):
    __tablename__ = 'loan_payment'
    
    loan_payment_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    loan_id = db.Column(BINARY(16), db.ForeignKey('loan.loan_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    payment_date = db.Column(db.DateTime, nullable=False)
    payment_amount = db.Column(db.DECIMAL(15,2), nullable=False)
    remaining_balance = db.Column(db.DECIMAL(15,2))

    __table_args__ = (
        db.CheckConstraint('payment_amount > 0', name='check_payment_positive'),
        db.CheckConstraint('remaining_balance >= 0', name='check_remaining_non_negative'),
    )
    
    def __repr__(self):
        return f"LoanPayment(loan_payment_id = {self.loan_payment_id}, loan_id = {self.loan_id}, payment_date = {self.payment_date}, payment_amount = {self.payment_amount}, remaining_balance = {self.remaining_balance})"

class Employee(db.Model):
    __tablename__ = 'employee'
    
    employee_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    branch_id = db.Column(BINARY(16), db.ForeignKey('branch.branch_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(100), nullable=False)
    hire_date = db.Column(db.DateTime, nullable=False)
    phone_number = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
        
    support_tickets = db.relationship('CustomerSupport', backref='employee', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"Employee(employee_id = {self.employee_id}, branch_id = {self.branch_id}, first_name = {self.first_name}, last_name = {self.last_name}, position = {self.position}, hire_date = {self.hire_date}, phone_number = {self.phone_number}, email = {self.email})"

class Card(db.Model):
    __tablename__ = 'card'
    
    card_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    account_id = db.Column(BINARY(16), db.ForeignKey('account.account_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    card_type = db.Column(db.Enum('DEBIT', 'CREDIT'), nullable=False)
    card_number = db.Column(db.String(16), unique=True, nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    cvv = db.Column(db.String(3), nullable=False)
    status = db.Column(db.Enum('ACTIVE', 'BLOCKED', 'EXPIRED'), nullable=False)
        
    def __repr__(self):
        return f"Card(card_id = {self.card_id}, account_id = {self.account_id}, card_type = {self.card_type}, card_number = {self.card_number}, expiration_date = {self.expiration_date}, cvv = {self.cvv}, status = {self.status})"

class Transaction(db.Model):
    __tablename__ = 'transaction'
    
    transaction_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    from_account_id = db.Column(BINARY(16), db.ForeignKey('account.account_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    to_account_id = db.Column(BINARY(16), db.ForeignKey('account.account_id', onupdate='CASCADE', ondelete='SET NULL'), nullable=False)
    transaction_type = db.Column(db.Enum('DEPOSIT', 'WITHDRAWAL', 'TRANSFER'), nullable=False)
    amount = db.Column(db.DECIMAL(15,2), nullable=False)
    transaction_timestamp = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='check_amount_positive'),
    )
        
    def __repr__(self):
        return f"Transaction(transaction_id = {self.transaction_id}, from_account_id = {self.from_account_id}, to_account_id = {self.to_account_id}, transaction_type = {self.transaction_type}, amount = {self.amount}, transaction_timestamp = {self.transaction_timestamp})"

class CustomerSupport(db.Model):
    __tablename__ = 'customer_support'
    
    ticket_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    employee_id = db.Column(BINARY(16), db.ForeignKey('employee.employee_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    issue_description = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum('OPEN', 'IN_PROGRESS', 'RESOLVED'), nullable=False)
    created_date = db.Column(db.DateTime, nullable=False)
    resolved_date = db.Column(db.DateTime)
        
    def __repr__(self):
        return f"CustomerSupport(ticket_id = {self.ticket_id}, customer_id = {self.customer_id}, employee_id = {self.employee_id}, issue_description = {self.issue_description}, status = {self.status}, created_date = {self.created_date}, resolved_date = {self.resolved_date})"

class CreditScore(db.Model):
    __tablename__ = 'credit_score'
    
    credit_score_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    customer_id = db.Column(BINARY(16), db.ForeignKey('customer.customer_id', onupdate='CASCADE', ondelete='RESTRICT'), nullable=False)
    score = db.Column(db.DECIMAL(5,2), nullable=False)
    risk_category = db.Column(db.String(50), nullable=False)
    computed_by_system = db.Column(db.Boolean)
        
    def __repr__(self):
        return f"CreditScore(credit_score_id = {self.credit_score_id}, customer_id = {self.customer_id}, score = {self.score}, risk_category = {self.risk_category}, computed_by_system = {self.computed_by_system})"
    
def validate_uuid(value):
    try:
        uuid.UUID(hex=value)
        return value
    except ValueError:
        raise ValueError('Invalid UUID format')

def validate_date(date_string):
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except ValueError:
        raise ValueError("Date must be in the format YYYY-MM-DD")

def validate_zip_code(zip_code):
    if re.fullmatch(r'^\d{5}(-\d{4})?$', zip_code):
        return zip_code
    raise ValueError("ZIP code must be in the format 12345 or 12345-6789")

def validate_email(email):
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if re.fullmatch(email_regex, email):
        return email
    raise ValueError("Invalid email address")

def validate_positive_number(value):
    try:
        value = float(value)
    except ValueError:
        raise ValueError("Value must be a number")
    if value <= 0:
        raise ValueError("Value must be greater than 0")
    return value

def validate_not_negative_number(value):
    try:
        value = float(value)
    except ValueError:
        raise ValueError("Value must be a number")
    if value < 0:
        raise ValueError("Value must be greater than or equal to 0")
    return value

def validate_card_number(card_number):
    if not re.fullmatch(r'^\d{13,19}$', card_number):
        raise ValueError("Card number must be 13 to 19 digits long")
    return card_number

def validate_cvv(cvv):
    if not re.fullmatch(r'^\d{3}$', cvv):
        raise ValueError("CVV must be 3 or 4 digits")
    return cvv

def validate_datetime(datetime_str, format="%Y-%m-%d %H:%M:%S"):
    """
    Validates a datetime string against a specified format.
    
    Args:
        datetime_str (str): The datetime string to validate.
        format (str): The expected datetime format. Default is '%Y-%m-%d %H:%M:%S'.
        
    Returns:
        datetime: A valid datetime object.
    
    Raises:
        ValueError: If the input string doesn't match the format.
    """
    try:
        return datetime.strptime(datetime_str, format)
    except ValueError:
        raise ValueError(f"Invalid datetime. Expected format: {format}")

def validate_phone_number(phone):
    phone_regex = r'^\+?[0-9\s\-()]{7,15}$'
    if not re.fullmatch(phone_regex, phone):
        raise ValueError("Invalid phone number format")
    return phone

user_args = reqparse.RequestParser()
user_args.add_argument('username', type=str, required=True, help='Username is required')
user_args.add_argument('password', type=str, required=True, help='Password is required')
user_args.add_argument('role', type=str, required=False, choices=('ADMIN', 'USER'), help='Role must be ADMIN or USER')
user_args.add_argument('customer_id', type=validate_uuid, required=False, help='Valid customer UUID is required')

branch_args = reqparse.RequestParser()
branch_args.add_argument('branch_name', type=str, required=True, help='Branch name is required')
branch_args.add_argument('address_line1', type=str, required=True, help='Address line 1 is required')
branch_args.add_argument('address_line2', type=str, required=False)
branch_args.add_argument('city', type=str, required=True, help='City is required')
branch_args.add_argument('zip_code', type=validate_zip_code, required=True, help='Zip code is required and must be in the format 12345 or 12345-6789')
branch_args.add_argument('phone_number', type=validate_phone_number, required=True, help='Valid phone number is required')

customer_args = reqparse.RequestParser()
customer_args.add_argument('first_name', type=str, required=True, help='First name is required')
customer_args.add_argument('last_name', type=str, required=True, help='Last name is required')
customer_args.add_argument('date_of_birth', type=validate_date, required=True, help='Date of birth is required and should be in format YYYY-MM-DD')
customer_args.add_argument('phone_number', type=validate_phone_number, required=True, help='Valid phone number is required')
customer_args.add_argument('email', type=validate_email, required=True, help='Email is required and should be valid')
customer_args.add_argument('address_line1', type=str, required=True, help='Address line 1 is required')
customer_args.add_argument('address_line2', type=str)
customer_args.add_argument('city', type=str, required=True, help='City is required')
customer_args.add_argument('zip_code', type=validate_zip_code, required=True, help='Zip code is required and must be in the format 12345 or 12345-6789')
customer_args.add_argument('wage_declaration', type=validate_not_negative_number, required=False, default=0, help='Wage declaration must be a non-negative number')

account_args = reqparse.RequestParser()
account_args.add_argument('customer_id', type=validate_uuid, required=True, help='Valid Customer UUID is required')
account_args.add_argument('account_type', type=str, choices=('CHECKING', 'SAVINGS'), required=True, help='Account type must be CHECKING or SAVINGS')
account_args.add_argument('balance', type=validate_not_negative_number, help='Balance must be >= 0', default=0.0)
account_args.add_argument('creation_date', type=validate_date, required=True, help='Creation date is required and should be in format YYYY-MM-DD')
account_args.add_argument('branch_id', type=validate_uuid, required=True, help='Valid Branch UUID is required')

loan_args = reqparse.RequestParser()
loan_args.add_argument('customer_id', type=validate_uuid, required=True, help='Valid Customer UUID is required')
loan_args.add_argument('loan_type', type=str, choices=('HOME', 'AUTO', 'PERSONAL'), required=True, help='Loan type is required and should be in "[HOME, AUTO, PERSONAL]"')
loan_args.add_argument('principal_amount', type=validate_positive_number, required=True, help='Principal amount is required and should be greater than 0')
loan_args.add_argument('interest_rate', type=validate_positive_number, required=True, help='Interest rate is required and should be greater than 0')
loan_args.add_argument('start_date', type=validate_date, required=True, help='Start date is required and should be in format YYYY-MM-DD')
loan_args.add_argument('end_date', type=validate_date, required=True, help='End date is required and should be in format YYYY-MM-DD')
loan_args.add_argument('status', type=str, choices=('ACTIVE', 'PAID_OFF', 'DEFAULT'), required=True, help='Status is required and should be in "[ACTIVE, PAID_OFF, DEFAULT]"')

loan_payment_args = reqparse.RequestParser()
loan_payment_args.add_argument('loan_id', type=validate_uuid, required=True, help='Valid Loan UUID is required')
loan_payment_args.add_argument('payment_date', type=validate_date, required=True, help='Payment date is required and should be in format YYYY-MM-DD')
loan_payment_args.add_argument('payment_amount', type=validate_positive_number, required=True, help='Payment amount is required and should not be less than 0')
loan_payment_args.add_argument('remaining_balance', type=validate_not_negative_number, help='Remaining balance should not be less than 0')

employee_args = reqparse.RequestParser()
employee_args.add_argument('branch_id', type=validate_uuid, required=True, help='Valid Branch UUID is required')
employee_args.add_argument('first_name', type=str, required=True, help='First name is required')
employee_args.add_argument('last_name', type=str, required=True, help='Last name is required')
employee_args.add_argument('position', type=str, required=True, help='Position is required')
employee_args.add_argument('hire_date', type=validate_date, required=True, help='Hire date is required and should be in format YYYY-MM-DD')
employee_args.add_argument('phone_number', type=validate_phone_number, required=True, help='Valid phone number is required')
employee_args.add_argument('email', type=validate_email, required=True, help='Email is required and should be valid')

card_args = reqparse.RequestParser()
card_args.add_argument('account_id', type=validate_uuid, required=True, help='Valid Account UUID is required')
card_args.add_argument('card_type', type=str, choices=('DEBIT','CREDIT'), required=True, help='Card type is required and should be in "[DEBIT, CREDIT]"')
card_args.add_argument('card_number', type=validate_card_number, required=True, help='Card number is required and should be valid')
card_args.add_argument('expiration_date', type=validate_date, required=True, help='Expiration date is required and should be in format YYYY-MM-DD')
card_args.add_argument('cvv', type=validate_cvv, required=True, help='CVV is required and should be 3 digits')
card_args.add_argument('status', type=str, choices=('ACTIVE','BLOCKED','EXPIRED'), required=True, help='Status is required and should be in "[ACTIVE, BLOCKED, EXPIRED]"')

transaction_args = reqparse.RequestParser()
transaction_args.add_argument('from_account_id', type=validate_uuid, required=True, help='Valid from account UUID is required')
transaction_args.add_argument('to_account_id', type=validate_uuid)
transaction_args.add_argument('transaction_type', type=str, choices=('DEPOSIT','WITHDRAWAL','TRANSFER'), required=True, help='Transaction type is required and should be in "[DEPOSIT,WITHDRAWAL,TRANSFER]"')
transaction_args.add_argument('amount', type=validate_positive_number, required=True, help='Amount is required and should be greater than 0')
transaction_args.add_argument('transaction_timestamp', type=validate_datetime, required=True, help='Transaction timestamp is required and should be in format "%Y-%m-%d %H:%M:%S"')

customer_support_args = reqparse.RequestParser()
customer_support_args.add_argument('customer_id', type=validate_uuid, required=True, help='Valid Customer UUID is required')
customer_support_args.add_argument('employee_id', type=validate_uuid, required=True, help='Valid Employee UUID is required')
customer_support_args.add_argument('issue_description', type=str, required=True, help='Issue description is required')
customer_support_args.add_argument('status', type=str, choices=('OPEN','IN_PROGRESS','RESOLVED'), required=True, help='Status is required and should be in "[OPEN, IN_PROGRESS, RESOLVED]"')
customer_support_args.add_argument('created_date', type=validate_datetime, required=True, help='Created date should be in format "%Y-%m-%d %H:%M:%S"')
customer_support_args.add_argument('resolved_date', type=validate_datetime, help='Resolved date should be in format "%Y-%m-%d %H:%M:%S"')

credit_score_args = reqparse.RequestParser()
credit_score_args.add_argument('customer_id', type=validate_uuid, required=True, help='Customer ID is required')
credit_score_args.add_argument('score', type=float, required=True, help='Credit score is required and should be a numeric value')
credit_score_args.add_argument('risk_category', type=str, required=True, help='Risk category is required')
credit_score_args.add_argument('computed_by_system', type=bool, help='Computed by system is required and should be a boolean')

money_transfer_args = reqparse.RequestParser()
money_transfer_args.add_argument('sender_account_id', type=validate_uuid, required=True, help='Sender account UUID is required')
money_transfer_args.add_argument('receiver_account_id', type=validate_uuid, required=True, help='Receiver account UUID is required')
money_transfer_args.add_argument('amount', type=validate_positive_number, required=True, help='Money amount is required')

loan_args.add_argument('customer_id', type=validate_uuid, required=True, help='Valid Customer UUID is required')
loan_args.add_argument('loan_type', type=str, choices=('HOME', 'AUTO', 'PERSONAL'), required=True, help='Loan type is required and should be in "[HOME, AUTO, PERSONAL]"')
loan_args.add_argument('principal_amount', type=validate_positive_number, required=True, help='Principal amount is required and should be greater than 0')
loan_args.add_argument('interest_rate', type=validate_positive_number, required=True, help='Interest rate is required and should be greater than 0')
loan_args.add_argument('start_date', type=validate_date, required=True, help='Start date is required and should be in format YYYY-MM-DD')
loan_args.add_argument('end_date', type=validate_date, required=True, help='End date is required and should be in format YYYY-MM-DD')
loan_args.add_argument('status', type=str, choices=('ACTIVE', 'PAID_OFF', 'DEFAULT'), required=True, help='Status is required and should be in "[ACTIVE, PAID_OFF, DEFAULT]"')


user_fields = {
    'user_id': fields.String,
    'username': fields.String,
    'password': fields.String,
    'role': fields.String,
    'customer_id': fields.String,
}

branch_fields = {
    'branch_id': fields.String,
    'branch_name': fields.String,
    'address_line1': fields.String,
    'address_line2': fields.String,
    'city': fields.String,
    'zip_code': fields.String,
    'phone_number': fields.String,
}

customer_fields = {
    'customer_id': fields.String,
    'first_name': fields.String,
    'last_name': fields.String,
    'date_of_birth': fields.String,
    'phone_number': fields.String,
    'email': fields.String,
    'address_line1': fields.String,
    'address_line2': fields.String,
    'city': fields.String,
    'zip_code': fields.String,
    'wage_declaration': fields.String,
}

account_fields = {
    'account_id': fields.String,
    'customer_id': fields.String,
    'account_type': fields.String,
    'balance': fields.Float,
    'creation_date': fields.DateTime,
    'branch_id': fields.String,
}

loan_fields = {
    'loan_id': fields.String,
    'customer_id': fields.String,
    'loan_type': fields.String,
    'principal_amount': fields.Float,
    'interest_rate': fields.Float,
    'start_date': fields.String,
    'end_date': fields.String,
    'status': fields.String,
}

loan_payment_fields = {
    'loan_payment_id': fields.String,
    'loan_id': fields.String,
    'payment_date': fields.String,
    'payment_amount': fields.Float,
    'remaining_balance': fields.Float,
}

employee_fields = {
    'employee_id': fields.String,
    'branch_id': fields.String,
    'first_name': fields.String,
    'last_name': fields.String,
    'position': fields.String,
    'hire_date': fields.DateTime,
    'phone_number': fields.String,
    'email': fields.String,
}

card_fields = {
    'card_id': fields.String,
    'account_id': fields.String,
    'card_type': fields.String,
    'card_number': fields.String,
    'expiration_date': fields.String,
    'cvv': fields.String,
    'status': fields.String,
}

transaction_fields = {
    'transaction_id': fields.String,
    'from_account_id': fields.String,
    'to_account_id': fields.String,
    'transaction_type': fields.String,
    'amount': fields.Float,
    'transaction_timestamp': fields.DateTime,
}

customer_support_fields = {
    'ticket_id': fields.String,
    'customer_id': fields.String,
    'employee_id': fields.String,
    'issue_description': fields.String,
    'status': fields.String,
    'created_date': fields.DateTime,
    'resolved_date': fields.DateTime,
}

credit_score_fields = {
    'credit_score_id': fields.String,
    'customer_id': fields.String,
    'score': fields.Float,
    'risk_category': fields.String,
    'computed_by_system': fields.Boolean,
}

class UserResourceAll(Resource):
    @marshal_with(user_fields)
    @admin_required
    def get(self):
        branch = User.query.all()
        return branch

    @marshal_with(user_fields)
    @admin_required
    def post(self):
        args = user_args.parse_args()
        user = User(
            username=args['username'], 
            password=args['password'], 
            role=args['role'], 
            customer_id=args['customer_id'] 
        )
        db.session.add(user)
        db.session.commit()
        users = User.query.all()
        return users, 201

class UserResource(Resource):
    @marshal_with(user_fields)
    @admin_required
    def get(self, user_id):
        user = User.query.filter_by(user_id=uuid.UUID(user_id).bytes).first()
        if not user:
            abort(404, message='User not found')
        return user
    
    @marshal_with(user_fields)
    @admin_required
    def put(self, user_id):
        args = user_args.parse_args()
        user = User.query.filter_by(user_id=uuid.UUID(user_id).bytes).first()
        if not user:
            abort(404, message='User not found')
        user.username = args['username']
        user.password = args['password']
        user.role = args['role']
        user.customer_id = args['customer_id']
        db.session.commit()
        return user
    
    @admin_required
    def delete(self, user_id):
        user = User.query.filter_by(user_id=uuid.UUID(user_id).bytes).first()
        if not user:
            abort(404, message='User not found')
        db.session.delete(user)
        db.session.commit()
        return {'message': f'User {user_id} deleted successfully'}, 200

class BranchResourceAll(Resource):
    @marshal_with(branch_fields)
    @admin_required
    def post(self):
        args = branch_args.parse_args()

        # Validate required fields
        missing_fields = [field for field in ['branch_name', 'address_line1', 'city', 'zip_code', 'phone_number'] if not args.get(field)]
        if missing_fields:
            return jsonify({
                'error': f"Missing required fields: {', '.join(missing_fields)}"
            }), 400

        # Check for duplicate branch name or phone number
        existing_branch = Branch.query.filter(
            (Branch.branch_name == args['branch_name']) |
            (Branch.phone_number == args['phone_number'])
        ).first()

        if existing_branch:
            message = []
            if existing_branch.branch_name == args['branch_name']:
                message.append(f"Branch name '{args['branch_name']}' already exists.")
            if existing_branch.phone_number == args['phone_number']:
                message.append(f"Phone number '{args['phone_number']}' already exists.")
            return jsonify({'error': ' '.join(message)}), 400

        # Try to create the new branch
        try:
            branch = Branch(
                branch_name=args['branch_name'],
                address_line1=args['address_line1'],
                address_line2=args.get('address_line2'),
                city=args['city'],
                zip_code=args['zip_code'],
                phone_number=args['phone_number']
            )
            db.session.add(branch)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f"Failed to create branch: {str(e)}"}), 500

        # Return all branches on success
        branches = Branch.query.all()
        return branches, 201



class BranchResource(Resource):
    @marshal_with(branch_fields)
    @admin_required
    def get(self, branch_id):
        branch = Branch.query.filter_by(branch_id=uuid.UUID(branch_id).bytes).first()
        if not branch:
            abort(404, message='Branch not found')
        return branch

    @marshal_with(branch_fields)
    @admin_required
    def put(self, branch_id):
        args = branch_args.parse_args()
        branch = Branch.query.filter_by(branch_id=uuid.UUID(branch_id).bytes).first()
        if not branch:
            abort(404, message='Branch not found')

        # Update branch details
        branch.branch_name = args['branch_name']
        branch.address_line1 = args['address_line1']
        branch.address_line2 = args['address_line2']
        branch.city = args['city']
        branch.zip_code = args['zip_code']
        branch.phone_number = args['phone_number']
        db.session.commit()
        return branch

    @admin_required
    def delete(self, branch_id):
        branch = Branch.query.filter_by(branch_id=uuid.UUID(branch_id).bytes).first()
        if not branch:
            abort(404, message='Branch not found')
        db.session.delete(branch)
        db.session.commit()
        return {'message': f'Branch {branch_id} deleted successfully'}, 200


class CustomerResourceAll(Resource):
    @marshal_with(customer_fields)
    @admin_required
    def get(self):
        customers = Customer.query.all()
        return customers
    
    @marshal_with(customer_fields)
    @admin_required
    def post(self):
        args = customer_args.parse_args()
        customer = Customer(
            first_name=args['first_name'], 
            last_name=args['last_name'], 
            date_of_birth=args['date_of_birth'], 
            phone_number=args['phone_number'], 
            email=args['email'], 
            address_line1=args['address_line1'], 
            address_line2=args['address_line2'], 
            city=args['city'], 
            zip_code=args['zip_code'], 
            wage_declaration=args['wage_declaration']
        )
        db.session.add(customer)
        db.session.commit()
        customers = Customer.query.all()
        return customers, 201

class CustomerResource(Resource):
    @marshal_with(customer_fields)
    @user_or_admin_required
    def get(self, customer_id):
        claims = get_jwt()
        if claims['role'] == 'USER' and claims['customer_id'] != customer_id:
            return {'error': 'Access denied'}, 403
        customer = Customer.query.filter_by(customer_id=customer_id).first()
        if not customer:
            abort(404, message='Customer not found')
        return customer
    
    @marshal_with(customer_fields)
    @admin_required
    def put(self, customer_id):
        args = customer_args.parse_args()
        customer = Customer.query.filter_by(customer_id=uuid.UUID(customer_id).bytes).first()
        if not customer:
            abort(404, message='Customer not found')
        customer.first_name = args['first_name']
        customer.last_name = args['last_name']
        customer.date_of_birth = args['date_of_birth']
        customer.phone_number = args['phone_number']
        customer.email = args['email']
        customer.address_line1 = args['address_line1']
        customer.address_line2 = args['address_line2']
        customer.city = args['city']
        customer.zip_code = args['zip_code']
        customer.wage_declaration = args['wage_declaration']
        db.session.commit()
        return customer
    
    @admin_required
    def delete(self, customer_id):
        customer = Customer.query.filter_by(customer_id=uuid.UUID(customer_id).bytes).first()
        if not customer:
            abort(404, message='Customer not found')
        db.session.delete(customer)
        db.session.commit()
        return {'message': f'Customer {customer_id} deleted successfully'}, 200

class AccountResourceAll(Resource):
    @marshal_with(account_fields)
    @admin_required
    def get(self):
        accounts = Account.query.all()
        return accounts
    
    @marshal_with(account_fields)
    @admin_required
    def post(self):
        args = account_args.parse_args()
        account = Account(
            customer_id=args['customer_id'], 
            account_type=args['account_type'], 
            balance=args['balance'],
            creation_date=args['creation_date'],
            branch_id=args['branch_id']
        )
        db.session.add(account)
        db.session.commit()
        accounts = Account.query.all()
        return accounts, 201

class AccountResource(Resource):
    @marshal_with(account_fields)
    @admin_required
    def get(self, account_id):
        account = Account.query.filter_by(account_id=uuid.UUID(account_id).bytes).first()
        if not account:
            abort(404, message='Account not found')
        return account
    
    @marshal_with(account_fields)
    @admin_required
    def put(self, account_id):
        args = account_args.parse_args()
        account = Account.query.filter_by(account_id=uuid.UUID(account_id).bytes).first()
        if not account:
            abort(404, message='Account not found')
        account.customer_id = args['customer_id']
        account.account_type = args['account_type']
        account.balance = args['balance']
        account.creation_date = args['creation_date']
        account.branch_id = args['branch_id']
        db.session.commit()
        return account
    
    @admin_required
    def delete(self, account_id):
        account = Account.query.filter_by(account_id=uuid.UUID(account_id).bytes).first()
        if not account:
            abort(404, message='Account not found')
        db.session.delete(account)
        db.session.commit()
        return {'message': f'Account {account_id} deleted successfully'}, 200

class LoanResourceAll(Resource):
    @marshal_with(loan_fields)
    @admin_required
    def get(self):
        loans = Loan.query.all()
        return loans
    
    @marshal_with(loan_fields)
    @admin_required
    def post(self):
        args = loan_args.parse_args()
        loan = Loan(
            customer_id=args['customer_id'], 
            loan_type=args['loan_type'], 
            principal_amount=args['principal_amount'], 
            interest_rate=args['interest_rate'], 
            start_date=args['start_date'], 
            end_date=args['end_date'], 
            status=args['status']
        )
        db.session.add(loan)
        db.session.commit()
        loans = Loan.query.all()
        return loans, 201
    
class LoanResource(Resource):
    @marshal_with(loan_fields)
    @admin_required
    def get(self, loan_id):
        loan = Loan.query.filter_by(loan_id=uuid.UUID(loan_id).bytes).first()
        if not loan:
            abort(404, message='Loan not found')
        return loan
    
    @marshal_with(loan_fields)
    @admin_required
    def put(self, loan_id):
        args = loan_args.parse_args()
        loan = Loan.query.filter_by(loan_id=uuid.UUID(loan_id).bytes).first()
        if not loan:
            abort(404, message='Loan not found')
        loan.customer_id = args['customer_id']
        loan.loan_type = args['loan_type']
        loan.principal_amount = args['principal_amount']
        loan.interest_rate = args['interest_rate']
        loan.start_date = args['start_date']
        loan.end_date = args['end_date']
        loan.status = args['status']
        db.session.commit()
        return loan
    
    @admin_required
    def delete(self, loan_id):
        loan = Loan.query.filter_by(loan_id=uuid.UUID(loan_id).bytes).first()
        if not loan:
            abort(404, message='Loan not found')
        db.session.delete(loan)
        db.session.commit()
        return {'message': f'Loan {loan_id} deleted successfully'}, 200

class LoanPaymentResourceAll(Resource):
    @marshal_with(loan_payment_fields)
    @admin_required
    def get(self):
        loan_payments = LoanPayment.query.all()
        return loan_payments
    
    @marshal_with(loan_payment_fields)
    @admin_required
    def post(self):
        args = loan_payment_args.parse_args()
        loan_payment = LoanPayment(
            loan_id=args['loan_id'], 
            payment_date=args['payment_date'], 
            payment_amount=args['payment_amount'], 
            remaining_balance=args['remaining_balance']
        )
        db.session.add(loan_payment)
        db.session.commit()
        loan_payments = LoanPayment.query.all()
        return loan_payments, 201
    
class LoanPaymentResource(Resource):
    @marshal_with(loan_payment_fields)
    @admin_required
    def get(self, loan_payment_id):
        loan_payment = LoanPayment.query.filter_by(loan_payment_id=uuid.UUID(loan_payment_id).bytes).first()
        if not loan_payment:
            abort(404, message='Loan payment not found')
        return loan_payment
    
    @marshal_with(loan_payment_fields)
    @admin_required
    def put(self, loan_payment_id):
        args = loan_payment_args.parse_args()
        loan_payment = LoanPayment.query.filter_by(loan_payment_id=uuid.UUID(loan_payment_id).bytes).first()
        if not loan_payment:
            abort(404, message='Loan payment not found')
        loan_payment.loan_id = args['loan_id']
        loan_payment.payment_date = args['payment_date']
        loan_payment.payment_amount = args['payment_amount']
        loan_payment.remaining_balance = args['remaining_balance']
        db.session.commit()
        return loan_payment
    
    @admin_required
    def delete(self, loan_payment_id):
        loan_payment = LoanPayment.query.filter_by(loan_payment_id=uuid.UUID(loan_payment_id).bytes).first()
        if not loan_payment:
            abort(404, message='Loan payment not found')
        db.session.delete(loan_payment)
        db.session.commit()
        return {'message': f'Loan payment {loan_payment_id} deleted successfully'}, 200
    
class EmployeeResourceAll(Resource):
    @marshal_with(employee_fields)
    @admin_required
    def get(self):
        employees = Employee.query.all()
        return employees
    
    @marshal_with(employee_fields)
    @admin_required
    def post(self):
        args = employee_args.parse_args()
        employee = Employee(
            branch_id=args['branch_id'], 
            first_name=args['first_name'], 
            last_name=args['last_name'], 
            position=args['position'], 
            hire_date=args['hire_date'],
            phone_number=args['phone_number'], 
            email=args['email']
        )
        db.session.add(employee)
        db.session.commit()
        employees = Employee.query.all()
        return employees, 201

class EmployeeResource(Resource):
    @marshal_with(employee_fields)
    @admin_required
    def get(self, employee_id):
        employee = Employee.query.filter_by(employee_id=uuid.UUID(employee_id).bytes).first()
        if not employee:
            abort(404, message='Employee not found')
        return employee
    
    @marshal_with(employee_fields)
    @admin_required
    def put(self, employee_id):
        args = employee_args.parse_args()
        employee = Employee.query.filter_by(employee_id=uuid.UUID(employee_id).bytes).first()
        if not employee:
            abort(404, message='Employee not found')
        employee.branch_id = args['branch_id']
        employee.first_name = args['first_name']
        employee.last_name = args['last_name']
        employee.position = args['position']
        employee.hire_date = args['hire_date']
        employee.phone_number = args['phone_number']
        employee.email = args['email']
        db.session.commit()
        return employee
    
    @admin_required
    def delete(self, employee_id):
        employee = Employee.query.filter_by(employee_id=uuid.UUID(employee_id).bytes).first()
        if not employee:
            abort(404, message='Employee not found')
        db.session.delete(employee)
        db.session.commit()
        return {'message': f'Employee {employee_id} deleted successfully'}, 200
    
class CardResourceAll(Resource):
    @marshal_with(card_fields)
    @admin_required
    def get(self):
        cards = Card.query.all()
        return cards
    
    @marshal_with(card_fields)
    def post(self):
        args = card_args.parse_args()
        card = Card(
            account_id=args['account_id'], 
            card_type=args['card_type'], 
            card_number=args['card_number'], 
            expiration_date=args['expiration_date'], 
            cvv=args['cvv'], 
            status=args['status']
        )
        db.session.add(card)
        db.session.commit()
        cards = Card.query.all()
        return cards, 201
    
class CardResource(Resource):
    @marshal_with(card_fields)
    @admin_required
    def get(self, card_id):
        card = Card.query.filter_by(card_id=uuid.UUID(card_id).bytes).first()
        if not card:
            abort(404, message='Card not found')
        return card
    
    @marshal_with(card_fields)
    @admin_required
    def put(self, card_id):
        args = card_args.parse_args()
        card = Card.query.filter_by(card_id=uuid.UUID(card_id).bytes).first()
        if not card:
            abort(404, message='Card not found')
        card.account_id = args['account_id']
        card.card_type = args['card_type']
        card.card_number = args['card_number']
        card.expiration_date = args['expiration_date']
        card.cvv = args['cvv']
        card.status = args['status']
        db.session.commit()
        return card
    
    @admin_required
    def delete(self, card_id):
        card = Card.query.filter_by(card_id=uuid.UUID(card_id).bytes).first()
        if not card:
            abort(404, message='Card not found')
        db.session.delete(card)
        db.session.commit()
        return {'message': f'Card {card_id} deleted successfully'}, 200
    
class TransactionResourceAll(Resource):
    @marshal_with(transaction_fields)
    @admin_required
    def get(self):
        transactions = Transaction.query.all()
        return transactions
    
    @marshal_with(transaction_fields)
    @admin_required
    def post(self):
        args = transaction_args.parse_args()
        transaction = Transaction(
            from_account_id=args['from_account_id'], 
            to_account_id=args['to_account_id'], 
            transaction_type=args['transaction_type'], 
            amount=args['amount'],
            transaction_timestamp=args['transaction_timestamp']
        )
        db.session.add(transaction)
        db.session.commit()
        transactions = Transaction.query.all()
        return transactions, 201
    
class TransactionResource(Resource):
    @marshal_with(transaction_fields)
    @admin_required
    def get(self, transaction_id):
        transaction = Transaction.query.filter_by(transaction_id=uuid.UUID(transaction_id).bytes).first()
        if not transaction:
            abort(404, message='Transaction not found')
        return transaction
    
    @marshal_with(transaction_fields)
    @admin_required
    def put(self, transaction_id):
        args = transaction_args.parse_args()
        transaction = Transaction.query.filter_by(transaction_id=uuid.UUID(transaction_id).bytes).first()
        if not transaction:
            abort(404, message='Transaction not found')
        transaction.from_account_id = args['from_account_id']
        transaction.to_account_id = args['to_account_id']
        transaction.transaction_type = args['transaction_type']
        transaction.amount = args['amount']
        transaction.transaction_timestamp = args['transaction_timestamp']
        db.session.commit()
        return transaction
    
    @admin_required
    def delete(self, transaction_id):
        transaction = Transaction.query.filter_by(transaction_id=uuid.UUID(transaction_id).bytes).first()
        if not transaction:
            abort(404, message='Transaction not found')
        db.session.delete(transaction)
        db.session.commit()
        return {'message': f'Transaction {transaction_id} deleted successfully'}, 200
    
class CustomerSupportResourceAll(Resource):
    @marshal_with(customer_support_fields)
    @admin_required
    def get(self):
        customer_supports = CustomerSupport.query.all()
        return customer_supports
    
    @marshal_with(customer_support_fields)
    @admin_required
    def post(self):
        args = customer_support_args.parse_args()
        customer_support = CustomerSupport(
            customer_id=args['customer_id'], 
            employee_id=args['employee_id'], 
            issue_description=args['issue_description'], 
            status=args['status'],
            created_date=args['created_date'], 
            resolved_date=args['resolved_date']
        )
        db.session.add(customer_support)
        db.session.commit()
        customer_supports = CustomerSupport.query.all()
        return customer_supports, 201
    
class CustomerSupportResource(Resource):
    @marshal_with(customer_support_fields)
    @admin_required
    def get(self, ticket_id):
        customer_support = CustomerSupport.query.filter_by(ticket_id=uuid.UUID(ticket_id).bytes).first()
        if not customer_support:
            abort(404, message='Customer support ticket not found')
        return customer_support
    
    @marshal_with(customer_support_fields)
    @admin_required
    def put(self, ticket_id):
        args = customer_support_args.parse_args()
        customer_support = CustomerSupport.query.filter_by(ticket_id=uuid.UUID(ticket_id).bytes).first()
        if not customer_support:
            abort(404, message='Customer support ticket not found')
        customer_support.customer_id = args['customer_id']
        customer_support.employee_id = args['employee_id']
        customer_support.issue_description = args['issue_description']
        customer_support.status = args['status']
        customer_support.created_date = args['created_date']
        customer_support.resolved_date = args['resolved_date']
        db.session.commit()
        return customer_support
    
    @admin_required
    def delete(self, ticket_id):
        customer_support = CustomerSupport.query.filter_by(ticket_id=uuid.UUID(ticket_id).bytes).first()
        if not customer_support:
            abort(404, message='Customer support ticket not found')
        db.session.delete(customer_support)
        db.session.commit()
        return {'message': f'Customer support ticket {ticket_id} deleted successfully'}, 200
    
class CreditScoreResourceAll(Resource):
    @marshal_with(credit_score_fields)
    @admin_required
    def get(self):
        credit_scores = CreditScore.query.all()
        return credit_scores
    
    @marshal_with(credit_score_fields)
    @admin_required
    def post(self):
        args = credit_score_args.parse_args()
        credit_score = CreditScore(
            customer_id=args['customer_id'], 
            score=args['score'], 
            risk_category=args['risk_category'], 
            computed_by_system=args['computed_by_system']
        )
        db.session.add(credit_score)
        db.session.commit()
        credit_scores = CreditScore.query.all()
        return credit_scores, 201
    
class CreditScoreResource(Resource):
    @marshal_with(credit_score_fields)
    @admin_required
    def get(self, credit_score_id):
        credit_score = CreditScore.query.filter_by(credit_score_id=uuid.UUID(credit_score_id).bytes).first()
        if not credit_score:
            abort(404, message='Credit score not found')
        return credit_score
    
    @marshal_with(credit_score_fields)
    @admin_required
    def put(self, credit_score_id):
        args = credit_score_args.parse_args()
        credit_score = CreditScore.query.filter_by(credit_score_id=uuid.UUID(credit_score_id).bytes).first()
        if not credit_score:
            abort(404, message='Credit score not found')
        credit_score.customer_id = args['customer_id']
        credit_score.score = args['score']
        credit_score.risk_category = args['risk_category']
        credit_score.computed_by_system = args['computed_by_system']
        db.session.commit()
        return credit_score
    
    @admin_required
    def delete(self, credit_score_id):
        credit_score = CreditScore.query.filter_by(credit_score_id=uuid.UUID(credit_score_id).bytes).first()
        if not credit_score:
            abort(404, message='Credit score not found')
        db.session.delete(credit_score)
        db.session.commit()
        return {'message': f'Credit score {credit_score_id} deleted successfully'}, 200
    
resources = [
    (UserResourceAll, '/api/user/'),
    (UserResource, '/api/user/<uuid:user_id>'),
    (BranchResourceAll, '/api/branch/'),
    (BranchResource, '/api/branch/<uuid:branch_id>'),
    (CustomerResourceAll, '/api/customer/'),
    (CustomerResource, '/api/customer/<uuid:customer_id>'),
    (AccountResourceAll, '/api/account/'),
    (AccountResource, '/api/account/<uuid:account_id>'),
    (LoanResourceAll, '/api/loan/'),
    (LoanResource, '/api/loan/<uuid:loan_id>'),
    (LoanPaymentResourceAll, '/api/loanpayment/'),
    (LoanPaymentResource, '/api/loanpayment/<uuid:loan_payment_id>'),
    (EmployeeResourceAll, '/api/employee/'),
    (EmployeeResource, '/api/employee/<uuid:employee_id>'),
    (CardResourceAll, '/api/card/'),
    (CardResource, '/api/card/<uuid:card_id>'),
    (TransactionResourceAll, '/api/transaction/'),
    (TransactionResource, '/api/transaction/<uuid:transaction_id>'),
    (CustomerSupportResourceAll, '/api/customersupport/'),
    (CustomerSupportResource, '/api/customersupport/<uuid:ticket_id>'),
    (CreditScoreResourceAll, '/api/creditscore/'),
    (CreditScoreResource, '/api/creditscore/<uuid:credit_score_id>')
]

for resource, route in resources:
    api.add_resource(resource, route)

def get_branches_with_conditions(min_employees=5, min_accounts=3):
    """
    Fetch branches with a minimum number of employees and accounts.

    :param min_employees: Minimum number of employees required (default is 5).
    :param min_accounts: Minimum number of accounts required (default is 3).
    :return: List of dictionaries containing branch names, employee counts, and account counts.
    """
    query = text("""
    SELECT B.branch_name, 
       COUNT(DISTINCT E.employee_id) AS employee_count, 
       COUNT(DISTINCT A.account_id) AS account_count 
        FROM branch B 
        LEFT JOIN employee E ON B.branch_id = E.branch_id 
        LEFT JOIN account A ON B.branch_id = A.branch_id 
        GROUP BY B.branch_name
        HAVING employee_count > :min_employees AND account_count >= :min_accounts;
    """)
    results = db.session.execute(query, {'min_employees': min_employees, 'min_accounts': min_accounts}).fetchall()
    return [dict(row) for row in results]

@app.route('/api/branches', methods=['GET'])
@admin_required
def api_branches_with_conditions():
    """
    API endpoint to fetch branches with a minimum number of employees and accounts.
    """
    min_employees = request.args.get('min_employees', default=5, type=int)
    min_accounts = request.args.get('min_accounts', default=3, type=int)

    if min_employees < 0 or min_accounts < 0:
        return jsonify({'error': 'Minimum values must be non-negative integers.'}), 400

    try:
        results = get_branches_with_conditions(min_employees, min_accounts)
        if results:
            return jsonify(results), 200
        else:
            return jsonify({'message': 'No branches found matching the specified criteria.'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_customers_with_high_transactions(min_transaction_total):
    """
    Fetch customers who made transactions totaling more than a specified amount.

    :param min_transaction_total: Minimum transaction total required (default is $10,000).
    :return: List of dictionaries containing customer details and total transaction amounts.
    """
    query = text("""
    SELECT C.customer_id, C.first_name, C.last_name, SUM(T.amount) AS total_transaction
    FROM customer C
    JOIN account A ON C.customer_id = A.customer_id
    JOIN "transaction" T ON A.account_id = T.from_account_id OR A.account_id = T.to_account_id
    GROUP BY C.customer_id, C.first_name, C.last_name
    HAVING SUM(T.amount) > :min_transaction_total;
    """)
    results = db.session.execute(query, {'min_transaction_total': min_transaction_total}).fetchall()
    return [dict(row) for row in results]

@app.route('/api/customer/high-transactions', methods=['GET'])
@admin_required
def api_customers_high_transactions():
    """
    API endpoint to fetch customers who made transactions totaling more than a specified amount.
    """
    min_transaction_total = request.args.get('min_transaction_total', type=float, default=10000)
    results = get_customers_with_high_transactions(min_transaction_total)
    if not results:
        return jsonify({'message': 'No customers found with transactions exceeding the specified amount.'}), 404
    return jsonify(results)

@app.route('/api/employee/top-resolvers', methods=['GET'])
@admin_required
def api_employees_top_resolvers():
    query = text("""
    WITH ResolvedTickets AS (
        SELECT E.employee_id, E.first_name, E.last_name, COUNT(CS.ticket_id) AS resolved_tickets
        FROM employee E
        JOIN customer_support CS ON E.employee_id = CS.employee_id
        WHERE CS.status = 'RESOLVED'
        GROUP BY E.employee_id, E.first_name, E.last_name
    )
    SELECT employee_id, first_name, last_name, resolved_tickets
    FROM ResolvedTickets
    WHERE resolved_tickets = (
        SELECT MAX(resolved_tickets) FROM ResolvedTickets
    );
    """)
    results = db.session.execute(query).fetchall()
    if not results:
        return jsonify({'message': 'No employees found with with meeting criteria.'}), 404
    return jsonify([dict(row) for row in results])

@app.route('/')
def home():
    return '<h1>Welcome to the Banking API!</h1>'

@app.route('/api/register', methods=['POST'])
def register():
    args = request.get_json()

    # Extract user fields
    username = args.get('username')
    password = args.get('password')
    role = args.get('role', 'USER')  # Default role is 'USER'

    # Extract customer fields
    first_name = args.get('first_name')
    last_name = args.get('last_name')
    try:
        date_of_birth = datetime.strptime(args.get('date_of_birth'), '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400
    phone_number = args.get('phone_number')
    email = args.get('email')
    address_line1 = args.get('address_line1')
    address_line2 = args.get('address_line2', None)
    city = args.get('city')
    zip_code = args.get('zip_code')
    wage_declaration = args.get('wage_declaration', 0.00)

    # Validate required fields
    if not (username and password and first_name and last_name and date_of_birth and phone_number and email and address_line1 and city and zip_code):
        return jsonify({'error': 'Missing required fields'}), 400

    # Check if username already exists
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists. Please choose another.'}), 400

    # Check if email already exists
    if Customer.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already exists. Please use another email.'}), 400

    # Check if phone_number already exists
    if Customer.query.filter_by(phone_number=phone_number).first():
        return jsonify({'error': 'Phone number already exists. Please use another phone number.'}), 400

    # Hash the password
    hashed_password = generate_password_hash(password)

    # Generate UUID for customer_id
    customer_id = generate_uuid()

    # Create new customer
    new_customer = Customer(
        customer_id=customer_id,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        phone_number=phone_number,
        email=email,
        address_line1=address_line1,
        address_line2=address_line2,
        city=city,
        zip_code=zip_code,
        wage_declaration=wage_declaration
    )
    db.session.add(new_customer)

    # Create new user linked to the customer
    new_user = User(
        username=username,
        password=hashed_password,
        role=role,
        customer_id=customer_id
    )
    db.session.add(new_user)

    # Commit transaction
    try:
        db.session.commit()
        return jsonify({'message': 'User and customer registered successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'An error occurred during registration. Please try again.'}), 500




@app.route('/api/login', methods=['POST'])
def login():

    try:
        args = user_args.parse_args()
        username = args['username']
        password = args['password']
    except Exception as e:
        return jsonify({'error': f'Invalid request: {str(e)}'}), 400

    # Fetch user from the database
    user = User.query.filter_by(username=username).one_or_none()
    if not user:
        return jsonify({'error': 'User does not exist'}), 401

    # Check password validity
    if not check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid password'}), 401

    # Prepare additional claims for the JWT
    additional_claims = {
        "username": user.username,
        "role": user.role,
        "customer_id": user.customer_id.hex() if user.customer_id else None
    }

    # Generate the access token
    try:
        access_token = create_access_token(identity=user.user_id.hex(), additional_claims=additional_claims)
    except Exception as e:
        return jsonify({'error': f'Failed to generate access token: {str(e)}'}), 500

    # Return the token
    return jsonify({'access_token': access_token}), 200


@app.route('/api/money-transfer', methods=['POST'])
@jwt_required
def money_transfer():
    identity = get_jwt()
    
    if not identity['customer_id']:
        return jsonify({'error': 'customer_id is None'}), 404

    sender_customer_id = uuid.UUID(hex=identity['customer_id']).bytes
    sender_customer = Customer.query.filter_by(customer_id=sender_customer_id).one_or_none()
    if not sender_customer:
        return jsonify({'error': 'No customer exists with this customer_id'}), 404
    
    args = money_transfer_args.parse_args()
    sender_account_id = args['sender_account_id']
    receiver_account_id = args['receiver_account_id']
    amount = args['amount']

    sender_account = Account.query.filter_by(account_id=uuid.UUID(hex=sender_account_id).bytes).one_or_none()
    if not sender_account:
        return jsonify({'error': 'No account exists with this account_id sender'}), 404
    
    if sender_account.customer_id != sender_customer_id:
        return jsonify({'error': 'Access denied: This account is not connected with claimed customer_id'}), 403

    receiver_account = Account.query.filter_by(account_id=uuid.UUID(hex=receiver_account_id).bytes).one_or_none()
    if not receiver_account:
        return jsonify({'error': 'No account exists with this account_id receiver'}), 404

    if sender_account.balance < amount:
        return jsonify({'error': 'Insufficient balance'})
    
    sender_account.balance -= amount
    receiver_account.balance += amount

    transaction_timestamp=datetime.now()
    
    new_transaction = Transaction(
        from_account_id=uuid.UUID(hex=sender_account_id).bytes,
        to_account_id=uuid.UUID(hex=receiver_account_id).bytes,
        transaction_type='TRANSFER',
        amount=amount,
        transaction_timestamp=transaction_timestamp
    )
    db.session.add(new_transaction)
    db.session.commit()

    return jsonify({
        'message': f'Money transfer is successfull',
        'sender_account_id': sender_account_id,
        'receiver_account_id': receiver_account_id,
        'transaction_type': 'TRANSFER',
        'amount': amount,
        'transaction_timestamp': transaction_timestamp
    }), 201

@app.route('/api/take-loan', methods=['POST'])
@jwt_required()
def take_loan():
    identity = get_jwt()

    customer_id_hex = identity.get('customer_id')
    if not customer_id_hex:
        return jsonify({'error': 'Customer ID not found for the user'}), 403

    args = loan_args.parse_args()

    customer_id = uuid.UUID(hex=customer_id_hex).bytes
    customer = Customer.query.filter_by(customer_id=customer_id).one_or_none()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    existing_loans = Loan.query.filter_by(customer_id=customer_id, status='ACTIVE').count()
    if existing_loans >= 1: 
        return jsonify({'error': 'Customer already has an active loan'}), 400

    # Create a new loan
    loan = Loan(
        customer_id=customer_id,
        loan_type=args['loan_type'],
        principal_amount=args['principal_amount'],
        interest_rate=args['interest_rate'],
        start_date=args['start_date'],
        end_date=args['end_date'],
        status='ACTIVE'
    )
    db.session.add(loan)
    db.session.commit()

    return jsonify({
        'message': 'Loan created successfully',
        'loan_id': loan.loan_id.hex(),
        'loan_details': {
            'loan_type': loan.loan_type,
            'principal_amount': loan.principal_amount,
            'interest_rate': loan.interest_rate,
            'start_date': loan.start_date.strftime('%Y-%m-%d'),
            'end_date': loan.end_date.strftime('%Y-%m-%d'),
            'status': loan.status
        }
    }), 201


if __name__ == '__main__':
    app.run(debug=True)