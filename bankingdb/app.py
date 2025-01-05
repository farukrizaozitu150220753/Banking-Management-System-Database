from flask import Flask
from routes import routes_blueprint
from database import init_db
from flask_jwt_extended import JWTManager
from flasgger import Swagger

app = Flask(__name__)

app.config['JWT_SECRET_KEY'] = 'super_secret_key'

jwt = JWTManager(app)

Swagger(app, template={
    "swagger": "2.0",
    "info": {
        "title": "Bank API",
        "description": "API documentation for the banking application.",
        "version": "1.0.0",
    },
    "host": "localhost:5000",
    "basePath": "/",
    "schemes": ["http", "https"],
})
# Initialize the database
init_db()

# Register blueprints
app.register_blueprint(routes_blueprint)

if __name__ == '__main__':
    app.run(debug=True)
