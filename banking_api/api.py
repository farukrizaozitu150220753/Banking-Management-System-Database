from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
from sqlalchemy import text
from sqlalchemy.dialects.mysql import BINARY
from flask_restful import Resource, Api, reqparse, fields, marshal_with, abort
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banking_management.db'
db = SQLAlchemy(app)
api = Api(app)

def generate_uuid():
    return uuid.uuid4().bytes

class Branch(db.Model):
    __tablename__ = 'branch'
    
    branch_id = db.Column(BINARY(16), primary_key=True, default=generate_uuid)
    branch_name = db.Column(db.String(100), unique=True, nullable=False)
    address_line1 = db.Column(db.String(100), nullable=False)
    address_line2 = db.Column(db.String(100))
    city = db.Column(db.String(100), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)

    # Relationships
    customers = db.relationship('Customer', backref='branch', cascade='all, delete-orphan')
    employees = db.relationship('Employee', backref='branch', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"Branch(branch_id = {self.branch_id}, branch_name = {self.branch_name}, address_line1 = {self.address_line1}, address_line2 = {self.address_line2}, city = {self.city}, zip_code = {self.zip_code}, phone_number = {self.phone_number})"

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
        uuid.UUID(value)
        return value
    except ValueError:
        raise ValueError('Invalid UUID format')

def validate_enum(allowed_values):
    def validate(value):
        if value not in allowed_values:
            raise ValueError(f'Value must be one of {allowed_values}')
        return value
    return validate

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

branch_args = reqparse.RequestParser()
branch_args.add_argument('branch_name', type=str, required=True, help='Branch name is required')
branch_args.add_argument('address_line1', type=str, required=True, help='Address line 1 is required')
branch_args.add_argument('address_line2', type=str, required=False)
branch_args.add_argument('city', type=str, required=True, help='City is required')
branch_args.add_argument('zip_code', type=validate_zip_code, required=True, help='Zip code is required and must be in the format 12345 or 12345-6789')
branch_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')

customer_args = reqparse.RequestParser()
customer_args.add_argument('first_name', type=str, required=True, help='First name is required')
customer_args.add_argument('last_name', type=str, required=True, help='Last name is required')
customer_args.add_argument('date_of_birth', type=validate_date, required=True, help='Date of birth is required and should be in format YYYY-MM-DD')
customer_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
customer_args.add_argument('email', type=validate_email, required=True, help='Email is required and should be valid')
customer_args.add_argument('address_line1', type=str, required=True, help='Address line 1 is required')
customer_args.add_argument('address_line2', type=str)
customer_args.add_argument('city', type=str, required=True, help='City is required')
customer_args.add_argument('zip_code', type=validate_zip_code, required=True, help='Zip code is required and must be in the format 12345 or 12345-6789')
customer_args.add_argument('wage_declaration', type=validate_not_negative_number, required=False, default=0, help='Wage declaration must be a non-negative number')

account_args = reqparse.RequestParser()
account_args.add_argument('customer_id', type=validate_uuid, required=True, help='Valid Customer UUID is required')
account_args.add_argument('account_type', type=validate_enum(['CHECKING', 'SAVINGS']), required=True, help='Account type must be CHECKING or SAVINGS')
account_args.add_argument('balance', type=validate_not_negative_number, help='Balance must be >= 0', default=0.0)
account_args.add_argument('creation_date', type=validate_date, required=True, help='Creation date is required and should be in format YYYY-MM-DD')
account_args.add_argument('branch_id', type=validate_uuid, required=True, help='Valid Branch UUID is required')

loan_args = reqparse.RequestParser()
loan_args.add_argument('customer_id', type=validate_uuid, required=True, help='Valid Customer UUID is required')
loan_args.add_argument('loan_type', type=validate_enum(['HOME', 'AUTO', 'PERSONAL']), required=True, help='Loan type is required and should be in "[HOME, AUTO, PERSONAL]"')
loan_args.add_argument('principal_amount', type=validate_positive_number, required=True, help='Principal amount is required and should be greater than 0')
loan_args.add_argument('interest_rate', type=validate_positive_number, required=True, help='Interest rate is required and should be greater than 0')
loan_args.add_argument('start_date', type=validate_date, required=True, help='Start date is required and should be in format YYYY-MM-DD')
loan_args.add_argument('end_date', type=validate_date, required=True, help='End date is required and should be in format YYYY-MM-DD')
loan_args.add_argument('status', type=validate_enum(['ACTIVE', 'PAID_OFF', 'DEFAULT']), required=True, help='Status is required and should be in "[ACTIVE, PAID_OFF, DEFAULT]"')

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
employee_args.add_argument('phone_number', type=str, required=True, help='Phone number is required')
employee_args.add_argument('email', type=validate_email, required=True, help='Email is required and should be valid')

card_args = reqparse.RequestParser()
card_args.add_argument('account_id', type=validate_uuid, required=True, help='Valid Account UUID is required')
card_args.add_argument('card_type', type=validate_enum(['DEBIT','CREDIT']), required=True, help='Card type is required and should be in "[DEBIT, CREDIT]"')
card_args.add_argument('card_number', type=validate_card_number, required=True, help='Card number is required and should be valid')
card_args.add_argument('expiration_date', type=validate_date, required=True, help='Expiration date is required and should be in format YYYY-MM-DD')
card_args.add_argument('cvv', type=validate_cvv, required=True, help='CVV is required and should be 3 digits')
card_args.add_argument('status', type=validate_enum(['ACTIVE','BLOCKED','EXPIRED']), required=True, help='Status is required and should be in "[ACTIVE, BLOCKED, EXPIRED]"')

transaction_args = reqparse.RequestParser()
transaction_args.add_argument('from_account_id', type=validate_uuid, required=True, help='Valid from account UUID is required')
transaction_args.add_argument('to_account_id', type=validate_uuid)
transaction_args.add_argument('transaction_type', type=validate_enum(['DEPOSIT','WITHDRAWAL','TRANSFER']), required=True, help='Transaction type is required and should be in "[DEPOSIT,WITHDRAWAL,TRANSFER]"')
transaction_args.add_argument('amount', type=validate_positive_number, required=True, help='Amount is required and should be greater than 0')
transaction_args.add_argument('transaction_timestamp', type=validate_datetime, required=True, help='Transaction timestamp is required and should be in format "%Y-%m-%d %H:%M:%S"')

customer_support_args = reqparse.RequestParser()
customer_support_args.add_argument('customer_id', type=validate_uuid, required=True, help='Valid Customer UUID is required')
customer_support_args.add_argument('employee_id', type=validate_uuid, required=True, help='Valid Employee UUID is required')
customer_support_args.add_argument('issue_description', type=str, required=True, help='Issue description is required')
customer_support_args.add_argument('status', type=validate_enum(['OPEN','IN_PROGRESS','RESOLVED']), required=True, help='Status is required and should be in "[OPEN, IN_PROGRESS, RESOLVED]"')
customer_support_args.add_argument('created_date', type=validate_datetime, required=True, help='Created date should be in format "%Y-%m-%d %H:%M:%S"')
customer_support_args.add_argument('resolved_date', type=validate_datetime, help='Resolved date should be in format "%Y-%m-%d %H:%M:%S"')

credit_score_args = reqparse.RequestParser()
credit_score_args.add_argument('customer_id', type=validate_uuid, required=True, help='Customer ID is required')
credit_score_args.add_argument('score', type=float, required=True, help='Credit score is required and should be a numeric value')
credit_score_args.add_argument('risk_category', type=str, required=True, help='Risk category is required')
credit_score_args.add_argument('computed_by_system', type=bool, help='Computed by system is required and should be a boolean')

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

class BranchResourceAll(Resource):
    @marshal_with(branch_fields)
    def get(self):
        branch = Branch.query.all()
        return branch

    @marshal_with(branch_fields)
    def post(self):
        args = branch_args.parse_args()
        branch = Branch(
            branch_name=args['branch_name'], 
            address_line1=args['address_line1'], 
            address_line2=args['address_line2'], 
            city=args['city'], 
            zip_code=args['zip_code'], 
            phone_number=args['phone_number']
        )
        db.session.add(branch)
        db.session.commit()
        branches = Branch.query.all()
        return branches, 201

class BranchResource(Resource):
    @marshal_with(branch_fields)
    def get(self, branch_id):
        branch = Branch.query.filter_by(branch_id=branch_id).first()
        if not branch:
            abort(404, message='Branch not found')
        return branch
    
    @marshal_with(branch_fields)
    def put(self, branch_id):
        args = branch_args.parse_args()
        branch = Branch.query.filter_by(branch_id=branch_id).first()
        if not branch:
            abort(404, message='Branch not found')
        branch.branch_name = args['branch_name']
        branch.address_line1 = args['address_line1']
        branch.address_line2 = args['address_line2']
        branch.city = args['city']
        branch.zip_code = args['zip_code']
        branch.phone_number = args['phone_number']
        db.session.commit()
        return branch
    
    def delete(self, branch_id):
        branch = Branch.query.filter_by(branch_id=branch_id).first()
        if not branch:
            abort(404, message='Branch not found')
        db.session.delete(branch)
        db.session.commit()
        return {'message': f'Branch {branch_id} deleted successfully'}, 200

class CustomerResourceAll(Resource):
    @marshal_with(customer_fields)
    def get(self):
        customers = Customer.query.all()
        return customers
    
    @marshal_with(customer_fields)
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
    def get(self, customer_id):
        customer = Customer.query.filter_by(customer_id=customer_id).first()
        if not customer:
            abort(404, message='Customer not found')
        return customer
    
    @marshal_with(customer_fields)
    def put(self, customer_id):
        args = customer_args.parse_args()
        customer = Customer.query.filter_by(customer_id=customer_id).first()
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
    
    def delete(self, customer_id):
        customer = Customer.query.filter_by(customer_id=customer_id).first()
        if not customer:
            abort(404, message='Customer not found')
        db.session.delete(customer)
        db.session.commit()
        return {'message': f'Customer {customer_id} deleted successfully'}, 200

class AccountResourceAll(Resource):
    @marshal_with(account_fields)
    def get(self):
        accounts = Account.query.all()
        return accounts
    
    @marshal_with(account_fields)
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
    def get(self, account_id):
        account = Account.query.filter_by(account_id=account_id).first()
        if not account:
            abort(404, message='Account not found')
        return account
    
    @marshal_with(account_fields)
    def put(self, account_id):
        args = account_args.parse_args()
        account = Account.query.filter_by(account_id=account_id).first()
        if not account:
            abort(404, message='Account not found')
        account.customer_id = args['customer_id']
        account.account_type = args['account_type']
        account.balance = args['balance']
        account.creation_date = args['creation_date']
        account.branch_id = args['branch_id']
        db.session.commit()
        return account
    
    def delete(self, account_id):
        account = Account.query.filter_by(account_id=account_id).first()
        if not account:
            abort(404, message='Account not found')
        db.session.delete(account)
        db.session.commit()
        return {'message': f'Account {account_id} deleted successfully'}, 200

class LoanResourceAll(Resource):
    @marshal_with(loan_fields)
    def get(self):
        loans = Loan.query.all()
        return loans
    
    @marshal_with(loan_fields)
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
    def get(self, loan_id):
        loan = Loan.query.filter_by(loan_id=loan_id).first()
        if not loan:
            abort(404, message='Loan not found')
        return loan
    
    @marshal_with(loan_fields)
    def put(self, loan_id):
        args = loan_args.parse_args()
        loan = Loan.query.filter_by(loan_id=loan_id).first()
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
    
    def delete(self, loan_id):
        loan = Loan.query.filter_by(loan_id=loan_id).first()
        if not loan:
            abort(404, message='Loan not found')
        db.session.delete(loan)
        db.session.commit()
        return {'message': f'Loan {loan_id} deleted successfully'}, 200

class LoanPaymentResourceAll(Resource):
    @marshal_with(loan_payment_fields)
    def get(self):
        loan_payments = LoanPayment.query.all()
        return loan_payments
    
    @marshal_with(loan_payment_fields)
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
    def get(self, loan_payment_id):
        loan_payment = LoanPayment.query.filter_by(loan_payment_id=loan_payment_id).first()
        if not loan_payment:
            abort(404, message='Loan payment not found')
        return loan_payment
    
    @marshal_with(loan_payment_fields)
    def put(self, loan_payment_id):
        args = loan_payment_args.parse_args()
        loan_payment = LoanPayment.query.filter_by(loan_payment_id=loan_payment_id).first()
        if not loan_payment:
            abort(404, message='Loan payment not found')
        loan_payment.loan_id = args['loan_id']
        loan_payment.payment_date = args['payment_date']
        loan_payment.payment_amount = args['payment_amount']
        loan_payment.remaining_balance = args['remaining_balance']
        db.session.commit()
        return loan_payment
    
    def delete(self, loan_payment_id):
        loan_payment = LoanPayment.query.filter_by(loan_payment_id=loan_payment_id).first()
        if not loan_payment:
            abort(404, message='Loan payment not found')
        db.session.delete(loan_payment)
        db.session.commit()
        return {'message': f'Loan payment {loan_payment_id} deleted successfully'}, 200
    
class EmployeeResourceAll(Resource):
    @marshal_with(employee_fields)
    def get(self):
        employees = Employee.query.all()
        return employees
    
    @marshal_with(employee_fields)
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
    def get(self, employee_id):
        employee = Employee.query.filter_by(employee_id=employee_id).first()
        if not employee:
            abort(404, message='Employee not found')
        return employee
    
    @marshal_with(employee_fields)
    def put(self, employee_id):
        args = employee_args.parse_args()
        employee = Employee.query.filter_by(employee_id=employee_id).first()
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
    
    def delete(self, employee_id):
        employee = Employee.query.filter_by(employee_id=employee_id).first()
        if not employee:
            abort(404, message='Employee not found')
        db.session.delete(employee)
        db.session.commit()
        return {'message': f'Employee {employee_id} deleted successfully'}, 200
    
class CardResourceAll(Resource):
    @marshal_with(card_fields)
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
    def get(self, card_id):
        card = Card.query.filter_by(card_id=card_id).first()
        if not card:
            abort(404, message='Card not found')
        return card
    
    @marshal_with(card_fields)
    def put(self, card_id):
        args = card_args.parse_args()
        card = Card.query.filter_by(card_id=card_id).first()
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
    
    def delete(self, card_id):
        card = Card.query.filter_by(card_id=card_id).first()
        if not card:
            abort(404, message='Card not found')
        db.session.delete(card)
        db.session.commit()
        return {'message': f'Card {card_id} deleted successfully'}, 200
    
class TransactionResourceAll(Resource):
    @marshal_with(transaction_fields)
    def get(self):
        transactions = Transaction.query.all()
        return transactions
    
    @marshal_with(transaction_fields)
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
    def get(self, transaction_id):
        transaction = Transaction.query.filter_by(transaction_id=transaction_id).first()
        if not transaction:
            abort(404, message='Transaction not found')
        return transaction
    
    @marshal_with(transaction_fields)
    def put(self, transaction_id):
        args = transaction_args.parse_args()
        transaction = Transaction.query.filter_by(transaction_id=transaction_id).first()
        if not transaction:
            abort(404, message='Transaction not found')
        transaction.from_account_id = args['from_account_id']
        transaction.to_account_id = args['to_account_id']
        transaction.transaction_type = args['transaction_type']
        transaction.amount = args['amount']
        transaction.transaction_timestamp = args['transaction_timestamp']
        db.session.commit()
        return transaction
    
    def delete(self, transaction_id):
        transaction = Transaction.query.filter_by(transaction_id=transaction_id).first()
        if not transaction:
            abort(404, message='Transaction not found')
        db.session.delete(transaction)
        db.session.commit()
        return {'message': f'Transaction {transaction_id} deleted successfully'}, 200
    
class CustomerSupportResourceAll(Resource):
    @marshal_with(customer_support_fields)
    def get(self):
        customer_supports = CustomerSupport.query.all()
        return customer_supports
    
    @marshal_with(customer_support_fields)
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
    def get(self, ticket_id):
        customer_support = CustomerSupport.query.filter_by(ticket_id=ticket_id).first()
        if not customer_support:
            abort(404, message='Customer support ticket not found')
        return customer_support
    
    @marshal_with(customer_support_fields)
    def put(self, ticket_id):
        args = customer_support_args.parse_args()
        customer_support = CustomerSupport.query.filter_by(ticket_id=ticket_id).first()
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
    
    def delete(self, ticket_id):
        customer_support = CustomerSupport.query.filter_by(ticket_id=ticket_id).first()
        if not customer_support:
            abort(404, message='Customer support ticket not found')
        db.session.delete(customer_support)
        db.session.commit()
        return {'message': f'Customer support ticket {ticket_id} deleted successfully'}, 200
    
class CreditScoreResourceAll(Resource):
    @marshal_with(credit_score_fields)
    def get(self):
        credit_scores = CreditScore.query.all()
        return credit_scores
    
    @marshal_with(credit_score_fields)
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
    def get(self, credit_score_id):
        credit_score = CreditScore.query.filter_by(credit_score_id=credit_score_id).first()
        if not credit_score:
            abort(404, message='Credit score not found')
        return credit_score
    
    @marshal_with(credit_score_fields)
    def put(self, credit_score_id):
        args = credit_score_args.parse_args()
        credit_score = CreditScore.query.filter_by(credit_score_id=credit_score_id).first()
        if not credit_score:
            abort(404, message='Credit score not found')
        credit_score.customer_id = args['customer_id']
        credit_score.score = args['score']
        credit_score.risk_category = args['risk_category']
        credit_score.computed_by_system = args['computed_by_system']
        db.session.commit()
        return credit_score
    
    def delete(self, credit_score_id):
        credit_score = CreditScore.query.filter_by(credit_score_id=credit_score_id).first()
        if not credit_score:
            abort(404, message='Credit score not found')
        db.session.delete(credit_score)
        db.session.commit()
        return {'message': f'Credit score {credit_score_id} deleted successfully'}, 200
    
resources = [
    (BranchResourceAll, '/api/branch/'),
    (BranchResource, '/api/branch/<int:branch_id>'),
    (CustomerResourceAll, '/api/customer/'),
    (CustomerResource, '/api/customer/<int:customer_id>'),
    (AccountResourceAll, '/api/account/'),
    (AccountResource, '/api/account/<int:account_id>'),
    (LoanResourceAll, '/api/loan/'),
    (LoanResource, '/api/loan/<int:loan_id>'),
    (LoanPaymentResourceAll, '/api/loanpayment/'),
    (LoanPaymentResource, '/api/loanpayment/<int:loan_payment_id>'),
    (EmployeeResourceAll, '/api/employee/'),
    (EmployeeResource, '/api/employee/<int:employee_id>'),
    (CardResourceAll, '/api/card/'),
    (CardResource, '/api/card/<int:card_id>'),
    (TransactionResourceAll, '/api/transaction/'),
    (TransactionResource, '/api/transaction/<int:transaction_id>'),
    (CustomerSupportResourceAll, '/api/customersupport/'),
    (CustomerSupportResource, '/api/customersupport/<int:ticket_id>'),
    (CreditScoreResourceAll, '/api/creditscore/'),
    (CreditScoreResource, '/api/creditscore/<int:credit_score_id>')
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
        FROM Branch B 
        LEFT JOIN Employee E ON B.branch_id = E.branch_id 
        LEFT JOIN Account A ON B.branch_id = A.branch_id 
        GROUP BY B.branch_name 
        HAVING employee_count > :min_employees AND account_count >= :min_accounts;
    """)
    results = db.session.execute(query, {'min_employees': min_employees, 'min_accounts': min_accounts}).fetchall()
    return [dict(row) for row in results]

@app.route('/api/branches', methods=['GET'])
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

def get_customers_with_high_transactions(min_transaction_total=10000):
    """
    Fetch customers who made transactions totaling more than a specified amount.

    :param min_transaction_total: Minimum transaction total required (default is $10,000).
    :return: List of dictionaries containing customer details and total transaction amounts.
    """
    query = text("""
    SELECT C.customer_id, C.first_name, C.last_name, SUM(T.amount) AS total_transaction
    FROM Customer C
    JOIN Account A ON C.customer_id = A.customer_id
    JOIN "Transaction" T ON A.account_id = T.from_account_id OR A.account_id = T.to_account_id
    GROUP BY C.customer_id, C.first_name, C.last_name
    HAVING SUM(T.amount) > :min_transaction_total;
    """)
    results = db.session.execute(query, {'min_transaction_total': min_transaction_total}).fetchall()
    return [dict(row) for row in results]

@app.route('/api/customer/high-transactions', methods=['GET'])
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
def api_employees_top_resolvers():
    query = text("""
    WITH ResolvedTickets AS (
        SELECT E.employee_id, E.first_name, E.last_name, COUNT(CS.ticket_id) AS resolved_tickets
        FROM Employee E
        JOIN Customer_Support CS ON E.employee_id = CS.employee_id
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
    return jsonify([dict(row) for row in results])

@app.route('/')
def home():
    return '<h1>Welcome to the Banking API!</h1>'

if __name__ == '__main__':
    app.run(debug=True)