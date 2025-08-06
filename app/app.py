from flask import Flask, render_template, request, url_for, flash, redirect, session, abort, g
import os
from flask_bootstrap import Bootstrap5
from peewee import *
from flask_sqlalchemy import SQLAlchemy
from config import Config


app = Flask(__name__)
bootstrap = Bootstrap5(app)

app.secret_key = 'super secret key'
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")
app.config['SESSION_TYPE'] = 'filesystem'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}
app.debug = True


db = PostgresqlDatabase('postgres', user='postgres', password='example', host='db', port=5432)


class BaseModel(Model):
    id = PrimaryKeyField(null=False, unique=True)

    class Meta:
        order_by = 'id'
        database = db


# class Cart(BaseModel):
#     name = CharField()
#
#     def add_to_cart(self, item):
#         self.items.append(item)
#
#     def get_items(self):
#         return items


# class Item(BaseModel):
#     name = CharField()
#     category = CharField(default="Food")
#     icon = TextField(default="/static/icons/placeholder.png")
#     cart = ManyToManyField(Cart, backref='cart')


@app.errorhandler(404)
def page_not_found(error):
    if session.get('logged_in'):
        return render_template('page_not_found.html', badge=None), 404
    else:
        return render_template('page_not_found.html', badge=None), 404


def object_list(template_name, qr, var_name='object_list', **kwargs):
    kwargs.update(
        page=int(request.args.get('page', 1)),
        pages=int(qr.count() / Config.REWARDS_PER_PAGE))
    kwargs[var_name] = qr.paginate(kwargs['page'], Config.REWARDS_PER_PAGE)
    return render_template(template_name, **kwargs)


@app.route('/')
def main():
    return render_template('main.html')


# @app.route('/join/')
# def join():
#     db.create_tables([Item, Cart])
#     # users = User.select().order_by(User.name)
#     print('DB created... I hope so')
#     # return render_template('join.html', users=users)
#     return render_template('main.html')


# @app.route('/items/')
# def items():
#     all_items = Item.select().order_by(Item.name)
#     return object_list('items.html', all_items, 'object_list')


# @app.route('/create/', methods=['GET', 'POST'])
# def create_event():
#     if request.method == 'POST':
#         name = request.form['title']
#         category = request.form['category']
#         if not name:
#             flash('Name is required!')
#         else:
#             Item.create(name=name, category=category)
#             flash('Your item is now exist!')
#             return redirect(url_for('items'))
#     return render_template('create_item.html')


# @app.route('/items/<int:item_id>', methods=['GET', 'POST'])
# def get_item(item_id):
#     if request.method == 'POST':
#         Item.delete_by_id(item_id)
#         return items()
#     else:
#         target_item = Item.get_by_id(item_id)
#         return render_template('item_info.html', item=target_item)


# @app.route('/items/<int:item_id>', methods=['POST'])
# def delete_item(item_id):
#     Item.delete_by_id(item_id)
#     print('Deleted?')
#     return render_template('items.html')


# @app.route('/cart/<int:cart_id>', methods=['GET'])
# def get_cart(cart_id):
#     cart = Cart.get_by_id(cart_id)
#     items = cart.get_items()
#     return object_list('cart.html', items, 'object_list')


# @app.route('/items/<int:item_id>', methods=['POST'])
# def add_to_card(item_id):
#     cart = Cart.create(name="Test")
#     item = Item.get_by_id(item_id)
#     cart.add_to_cart(item)
#     items = cart.get_items()
#     return object_list('cart.html', items, 'object_list')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    app.run(debug=True)
