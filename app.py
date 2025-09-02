import os
import sys
import click
from flask_migrate import Migrate, upgrade
from app import create_app, db
from app.models import User, Role

app = create_app('default')
migrate = Migrate(app, db)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    app.run(debug=True)


@app.shell_context_processor
def make_shell_context():
    return dict(db=db, User=User, Role=Role)
